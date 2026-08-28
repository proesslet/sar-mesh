"""Entry point for the frozen application.

A packaged SARMesh is launched by double-clicking, so with no arguments it goes
straight to the desktop app. Arguments still work when the bundle is started
from a shortcut or a terminal -- `--basemap` in particular, which is the only
way to load offline tiles until the UI can pick a file itself.

What a packaged build does not have is a console: it is built windowed, so on
Windows there is no stdout at all and a double-clicked macOS .app has none
worth reading. Nothing here may rely on printing. Diagnostics go to the log
file (see sarmesh.diagnostics), and anything fatal also raises a dialog --
without one, a bundle that fails to start looks exactly like a bundle that was
never launched.

Managing incidents, teams and trackers from the command line is meant for a
source checkout or an installed wheel (`uv run sarmesh ...`), where output can
actually be read.
"""

import logging
import multiprocessing
import sys

from sarmesh.cli import app
from sarmesh.diagnostics import configure_logging, report_fatal_error

if __name__ == "__main__":
    # Required before any threads start, or a frozen child process on Windows
    # re-executes the whole program instead of the worker.
    multiprocessing.freeze_support()

    # Ahead of app() so that a failure during argument parsing still lands
    # somewhere readable. The CLI callback calls this again; it is idempotent.
    configure_logging()

    if len(sys.argv) == 1:
        sys.argv.append("app")

    try:
        app()
    except Exception as error:
        # SystemExit and KeyboardInterrupt are deliberately not caught: typer
        # exits through the first, and the second is a clean shutdown.
        logging.getLogger("sarmesh").exception("SARMesh exited unexpectedly")
        report_fatal_error(f"SARMesh could not start: {error}")
        sys.exit(1)
