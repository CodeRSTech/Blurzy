# lab.py
from PySide6.QtWidgets import QApplication

from app.application.application import Application
from app.ui.qt.main_window import MainWindow
from app.ui.uicontroller import UIController

# Safely get or create the QApplication
qapp = QApplication.instance() or QApplication([])

# Initialize your Clean Architecture stack
app = Application()
window = MainWindow()
controller = UIController(q_app=qapp, window=window, app=app)

# Show the window (IPython will keep it alive)
window.show()

print("\n--- Welcome to the UI Lab ---")
print("Available objects: 'app', 'window', 'controller', 'qapp'")