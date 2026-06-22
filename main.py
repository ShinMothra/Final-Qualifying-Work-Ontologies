import sys
import os

if getattr(sys, "frozen", False):
    APP_ROOT = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
else:
    APP_ROOT = os.path.dirname(os.path.abspath(__file__))

os.chdir(APP_ROOT)
sys.path.insert(0, APP_ROOT)

from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())