import contextlib
import logging
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from sarmesh.core.events import PositionBroadcaster
from sarmesh.services.basemaps import BasemapDownloader
from sarmesh.services.tracking import TrackingService
from sarmesh.storage.database import Database
from sarmesh.storage.paths import basemap_dir
from sarmesh.transports import PositionHandler, Transport, TransportFactory
from sarmesh.transports.meshtastic import MeshtasticTransport
from sarmesh.web.server import create_app
from sarmesh.web.tiles import BASEMAP_SETTING, BasemapLibrary

QT_HINT = """
The desktop window needs PySide6, which bundles its own rendering engine:

    uv sync

On Raspberry Pi this needs Pi OS Trixie or newer, since the ARM wheels want
glibc 2.39 and Bookworm ships 2.36.
"""

# What the app uses when no port is asked for. Also what the Vite dev server
# proxies to, so the default has to stay predictable rather than always being
# an ephemeral one.
DEFAULT_HTTP_PORT = 8000

logger = logging.getLogger(__name__)


def _listen(host: str, port: int) -> socket.socket:
    """Bind a listening socket, or raise OSError if the port is taken."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    if sys.platform != "win32":
        # Lets a restart rebind a port still in TIME_WAIT. Deliberately not
        # set on Windows, where SO_REUSEADDR permits binding over a live
        # listener: it would steal the port instead of reporting the clash.
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        sock.bind((host, port))
    except OSError:
        sock.close()
        raise

    return sock


class DesktopApp:
    """Runs the HTTP server, the radio listener, and the desktop window.

    Three things need threads here: uvicorn's event loop, the Meshtastic
    reader, and the native window. The window must own the main thread, since
    macOS and GTK both require their UI loop to run there, so the server and
    the radio go to background threads.
    """

    def __init__(
        self,
        database_path: Path,
        host: str = "127.0.0.1",
        port: int | None = None,
        basemap: Path | None = None,
        radio_host: str | None = None,
        radio_port: int | None = None,
        offline: bool = False,
        transport_factory: TransportFactory | None = None,
    ) -> None:
        self.host = host
        # None means "prefer the default port, but settle for any free one".
        # The port actually bound is not known until run().
        self.requested_port = port
        self.port = port if port is not None else DEFAULT_HTTP_PORT
        self.offline = offline
        self.radio_host = radio_host
        self.radio_port = radio_port

        self.database = Database(database_path)
        self.database.migrate()

        self.broadcaster = PositionBroadcaster()
        self.tracking_service = TrackingService(
            database=self.database,
            broadcaster=self.broadcaster,
        )

        # --basemap wins for this run; otherwise the pack chosen in a previous
        # session is restored, so a map picked in settings is still there after
        # a restart.
        self.basemaps = BasemapLibrary(basemap_dir(), pinned=basemap)
        self.basemaps.select_default(self.database.settings.get(BASEMAP_SETTING))

        self.downloader = BasemapDownloader()

        # Swappable so the incident simulator can feed synthetic positions
        # through the same path a radio uses. Defaults to the real Meshtastic
        # transport, which is the only one a packaged build ever builds.
        self.transport_factory = transport_factory or self._meshtastic
        self.transport: Transport | None = None

        self._api = create_app(
            self.database, self.broadcaster, self.basemaps, self.downloader
        )
        self._server: uvicorn.Server | None = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def _bind(self) -> socket.socket:
        """Claim the port to serve on, before anything is told the URL."""
        # An explicit --http-port was promised to something else (the Vite dev
        # proxy, a bookmark), so a clash there is an error. Without one, any
        # free port will do: the window is handed the URL either way.
        if self.requested_port is not None:
            return _listen(self.host, self.requested_port)

        try:
            return _listen(self.host, DEFAULT_HTTP_PORT)
        except OSError:
            logger.info(
                "Port %d is already in use; serving on a free port instead",
                DEFAULT_HTTP_PORT,
            )
            return _listen(self.host, 0)

    def _meshtastic(self, on_position: PositionHandler) -> Transport:
        return MeshtasticTransport(
            on_position=on_position,
            host=self.radio_host,
            port=self.radio_port,
        )

    def _start_radio(self) -> None:
        transport = self.transport_factory(self.tracking_service.handle_position)

        try:
            transport.start()
        except ConnectionError as error:
            # A missing radio must not take the UI down. An operator still
            # needs the last known positions and the team lists.
            logger.warning(
                "Radio unavailable, running without live positions: %s", error
            )
            return

        self.transport = transport

    def run(self, window: bool = True) -> None:
        try:
            sock = self._bind()
        except OSError as error:
            raise ConnectionError(
                f"Could not serve the UI on port {self.port}: {error}"
            ) from error

        # Binding here rather than inside uvicorn means the real port is known
        # before anything is started, so no one is ever shown a URL that turns
        # out to belong to another process.
        self.port = sock.getsockname()[1]

        self._server = uvicorn.Server(
            uvicorn.Config(
                self._api,
                host=self.host,
                port=self.port,
                # uvicorn's default config logs to stdout, which does not exist
                # in a windowed build. Its loggers reach the log file through
                # the root logger instead.
                log_config=None,
                access_log=False,
            )
        )

        server_thread = threading.Thread(
            target=self._server.run,
            kwargs={"sockets": [sock]},
            daemon=True,
            name="http",
        )
        server_thread.start()

        # uvicorn still reports a startup failure on its own thread, so wait for
        # it to confirm rather than assuming a successful bind was enough.
        if not self._wait_for_server(server_thread):
            sock.close()
            raise ConnectionError(f"The UI server did not start on {self.url}")

        # A packaged build does not write beside the executable, so say where
        # the incident data actually lives.
        logger.info("Database: %s", self.database.path)
        logger.info("SARMesh serving at %s", self.url)

        if not self.offline:
            threading.Thread(
                target=self._start_radio, daemon=True, name="radio"
            ).start()

        try:
            if window:
                self._run_window()
            else:
                print(f"SARMesh running at {self.url}  (Ctrl-C to stop)")
                threading.Event().wait()
        except KeyboardInterrupt:
            logger.info("Shutting down")
        finally:
            self.shutdown()

    def _wait_for_server(self, thread: threading.Thread, timeout: float = 15.0) -> bool:
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if self._server is not None and self._server.started:
                return True

            # A bind failure ends the thread rather than raising to us.
            if not thread.is_alive():
                return False

            time.sleep(0.05)

        return False

    def _run_window(self) -> None:
        try:
            from sarmesh.desktop import run_window
        except ImportError as error:
            # Qt missing entirely. Fall back rather than exit, so an operator
            # keeps access to stored positions.
            logger.error("Native window unavailable: %s", error)
            logger.info(QT_HINT)
            self._serve_only()
            return

        run_window(self.url)

    def _serve_only(self) -> None:
        with contextlib.suppress(Exception):
            webbrowser.open(self.url)

        print(f"\nSARMesh running at {self.url}  (Ctrl-C to stop)")
        threading.Event().wait()

    def shutdown(self) -> None:
        # None if run() failed before the server was built; the rest of the
        # teardown still has to happen.
        if self._server is not None:
            self._server.should_exit = True

        if self.transport is not None:
            self.transport.stop()

        # Stops a download mid-flight rather than leaving its worker threads
        # fetching tiles into a file nothing will finish writing.
        self.downloader.cancel()
        self.basemaps.close()

        self.database.close()
