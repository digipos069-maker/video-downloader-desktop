import sys
import os
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QVBoxLayout, QWidget, QSizeGrip
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from app.ui.downloader_tab import DownloaderTab
from app.ui.settings_tab import SettingsTab
from app.ui.widgets.title_bar import TitleBar
from app.config.settings_manager import save_settings
from app.helpers import resource_path

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Social download manager")
        self.resize(1280, 720)
        
        # Frameless window for custom title bar
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground) # Optional, for rounded corners if needed

        # Central Widget Wrapper
        central_widget = QWidget()
        central_widget.setObjectName("MainCentralWidget") # For styling if needed
        self.setCentralWidget(central_widget)

        # Main Layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Custom Title Bar
        self.title_bar = TitleBar(self, title="Social download manager")
        main_layout.addWidget(self.title_bar)

        # Create a central tab widget
        self.tabs = QTabWidget()
        self.tabs.setIconSize(QSize(24, 24))
        main_layout.addWidget(self.tabs)

        # Add the downloader tab
        self.downloader_tab = DownloaderTab()
        self.tabs.addTab(self.downloader_tab, QIcon(resource_path("app/resources/images/icons/download.png")), "Downloader")

        # Add the settings tab
        self.settings_tab = SettingsTab()
        self.tabs.addTab(self.settings_tab, QIcon(resource_path("app/resources/images/icons/settings.png")), "Settings")
        
        # Connect settings to downloader
        self.downloader_tab.set_settings_tab(self.settings_tab)

        # Size Grip (Bottom Right Resizing)
        self.size_grip = QSizeGrip(self)
        self.size_grip.setStyleSheet("width: 20px; height: 20px; margin: 5px; background-color: transparent;")

    def resizeEvent(self, event):
        # Position the size grip at the bottom right
        rect = self.rect()
        self.size_grip.move(rect.right() - self.size_grip.width(), rect.bottom() - self.size_grip.height())
        super().resizeEvent(event)

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
    style_file = resource_path(os.path.join("app", "resources", "styles.qss"))
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