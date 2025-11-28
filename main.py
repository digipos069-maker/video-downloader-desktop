import sys
import os
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget
from app.ui.downloader_tab import DownloaderTab
from app.ui.settings_tab import SettingsTab

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Universal Video Downloader")
        self.resize(1280, 720)

        # Create a central tab widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Add the downloader tab
        self.downloader_tab = DownloaderTab()
        self.tabs.addTab(self.downloader_tab, "Downloader")

        # Add the settings tab
        self.settings_tab = SettingsTab()
        self.tabs.addTab(self.settings_tab, "Settings")


def main():
    """
    The main function to run the application.
    """
    app = QApplication(sys.argv)

    # Load and apply stylesheet
    style_file = os.path.join(os.path.dirname(__file__), "app", "resources", "styles.qss")
    if os.path.exists(style_file):
        with open(style_file, "r") as f:
            app.setStyleSheet(f.read())
    else:
        print(f"Warning: Stylesheet not found at {style_file}")


    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()