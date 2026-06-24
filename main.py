import sys
import ctypes
from pathlib import Path

from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication
from qfluentwidgets import Theme, setTheme, setThemeColor

from ui.main_window import MainWindow

APP_NAME = "Yeelight Sync Pro"
APP_USER_MODEL_ID = "Yeelight.Sync.Pro"


def qt_message_handler(mode, context, message):
    if "QFont::setPointSize: Point size <= 0 (-1)" in message:
        return
    sys.__stderr__.write(message + "\n")


def main() -> int:
    qInstallMessageHandler(qt_message_handler)
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setDesktopFileName(APP_USER_MODEL_ID)
    app.setOrganizationName("Yeelight Sync")
    app.setFont(QFont("Microsoft YaHei UI", 10))

    setTheme(Theme.AUTO)
    setThemeColor("#0A84FF")

    icon_path = Path(__file__).with_name("icon.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
