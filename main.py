import sys
import os
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget
from app.ui.downloader_tab import DownloaderTab
from app.ui.settings_tab import SettingsTab
from app.config.settings_manager import save_settings

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
        
        # Connect settings to downloader
        self.downloader_tab.set_settings_tab(self.settings_tab)

    def closeEvent(self, event):
        """Handle application closure to save settings."""
        try:
            # Gather settings from tabs
            settings_tab_data = self.settings_tab.get_settings()
            downloader_tab_data = self.downloader_tab.get_ui_state()
            
            # Merge settings
            full_settings = {**settings_tab_data, **downloader_tab_data}
            
            # Save to file
            save_settings(full_settings)
            # print("Settings saved on exit.")
        except Exception as e:
            print(f"Error saving settings on exit: {e}")
            
        event.accept()


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