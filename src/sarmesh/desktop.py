import sys
from collections.abc import Callable

from PySide6.QtCore import QUrl
from PySide6.QtGui import QCloseEvent
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox

WINDOW_TITLE = "SARMesh"


class MainWindow(QMainWindow):
    """A native window hosting the SARMesh UI.

    The UI is loaded over the local HTTP server rather than from file:// so
    that the API, the SSE position stream, and the tile endpoint all share one
    origin, and so the same build can be viewed from another device on the
    network without a second code path.
    """

    def __init__(self, url: str, on_close: Callable[[], None] | None = None) -> None:
        super().__init__()

        self._on_close = on_close

        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1280, 800)

        self.view = QWebEngineView(self)
        self.view.load(QUrl(url))
        self.setCentralWidget(self.view)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._on_close is not None:
            self._on_close()

        super().closeEvent(event)


def run_window(url: str, on_close: Callable[[], None] | None = None) -> None:
    """Run the desktop window. Blocks until the window is closed.

    Must be called on the main thread; Qt requires its event loop to own it.
    """
    app = QApplication.instance() or QApplication(sys.argv)

    window = MainWindow(url, on_close=on_close)
    window.show()

    app.exec()  # type: ignore[union-attr]


def show_error(message: str) -> None:
    """Show a modal error dialog and block until it is dismissed.

    A windowed build has no console, so without this an operator who
    double-clicks a bundle that cannot start sees nothing happen at all.
    """
    # There is normally no QApplication yet: this runs on startup paths that
    # failed before the window was ever created.
    QApplication.instance() or QApplication(sys.argv)

    box = QMessageBox()
    box.setIcon(QMessageBox.Icon.Critical)
    box.setWindowTitle(WINDOW_TITLE)
    box.setText(message)
    box.exec()
