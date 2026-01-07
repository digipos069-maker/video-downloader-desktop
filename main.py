import sys
import os
import time
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QVBoxLayout, QWidget, QSizeGrip, QSplashScreen
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QFont, QColor
from app.ui.downloader_tab import DownloaderTab
from app.ui.settings_tab import SettingsTab
from app.ui.widgets.title_bar import TitleBar
from app.config.settings_manager import save_settings
from app.helpers import resource_path, get_app_path

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Social download manager")
        self.resize(1280, 720)
        
        # Set Window Icon
        logo_path = resource_path(os.path.join("app", "resources", "images", "logo.png"))
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))
        
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
    # Ensure local directory is in PATH for finding ffmpeg.exe etc.
    app_path = get_app_path()
    os.environ["PATH"] += os.pathsep + app_path
    
    # Ensure Playwright can find browsers (Critical for Frozen/EXE)
    # 1. Check for bundled browsers next to executable or in _internal
    bundled_browsers = os.path.join(app_path, 'playwright-browsers')
    internal_browsers = os.path.join(app_path, '_internal', 'playwright-browsers')
    
    if os.path.exists(bundled_browsers):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = bundled_browsers
        # print(f"Using bundled browsers at: {bundled_browsers}")
    elif os.path.exists(internal_browsers):
         os.environ["PLAYWRIGHT_BROWSERS_PATH"] = internal_browsers
         # print(f"Using internal browsers at: {internal_browsers}")
    elif "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
        # 2. Fallback: Default location on Windows (Development / User Install)
        default_pw_path = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'ms-playwright')
        if os.path.exists(default_pw_path):
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = default_pw_path
            # print(f"Set PLAYWRIGHT_BROWSERS_PATH to: {default_pw_path}")
    
    app = QApplication(sys.argv)
    
    # --- Set App Icon (Taskbar & Window) ---
    logo_path = resource_path(os.path.join("app", "resources", "images", "logo.png"))
    if os.path.exists(logo_path):
        app_icon = QIcon(logo_path)
        app.setWindowIcon(app_icon)
        
        # Windows Taskbar Icon Fix (App User Model ID)
        if sys.platform == 'win32':
            import ctypes
            myappid = 'com.video.downloader.sdm.v1' # Arbitrary string
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    
    # --- Splash Screen Setup ---
    # Create a pixmap for the splash screen
    splash_pix = QPixmap(400, 300)
    splash_pix.fill(QColor("#101014")) # Background color matching the theme

    painter = QPainter(splash_pix)
    
    # Load and draw logo
    logo_path = resource_path(os.path.join("app", "resources", "images", "logo.png"))
    if os.path.exists(logo_path):
        logo = QPixmap(logo_path)
        logo = logo.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
        # Center the logo
        logo_x = (splash_pix.width() - logo.width()) // 2
        logo_y = (splash_pix.height() - logo.height()) // 2 - 20 # Slightly shifted up
        painter.drawPixmap(logo_x, logo_y, logo)
    else:
        # Fallback if logo missing
        logo_y = 100 

    # Draw "SDM" text
    painter.setPen(QColor("#3B82F6")) # Accent Blue
    font = QFont("Segoe UI", 32, QFont.Bold)
    painter.setFont(font)
    
    text = "SDM"
    font_metrics = painter.fontMetrics()
    text_width = font_metrics.horizontalAdvance(text)
    text_x = (splash_pix.width() - text_width) // 2
    text_y = logo_y + 100 + 40 # Below logo
    
    painter.drawText(text_x, text_y, text)

    # Draw "Loading..." text
    font_loading = QFont("Segoe UI", 10)
    painter.setFont(font_loading)
    painter.setPen(QColor("#71717A")) # Zinc-500 Gray
    loading_text = "Loading..."
    loading_metrics = painter.fontMetrics()
    loading_width = loading_metrics.horizontalAdvance(loading_text)
    loading_x = (splash_pix.width() - loading_width) // 2
    loading_y = text_y + 35
    painter.drawText(loading_x, loading_y, loading_text)

    painter.end()

    # Show Splash
    splash = QSplashScreen(splash_pix, Qt.WindowStaysOnTopHint)
    splash.show()
    app.processEvents()

    # Load and apply stylesheet
    style_file = resource_path(os.path.join("app", "resources", "styles.qss"))
    if os.path.exists(style_file):
        with open(style_file, "r") as f:
            app.setStyleSheet(f.read())
    else:
        print(f"Warning: Stylesheet not found at {style_file}")

    # Simulate initialization delay (for effect)
    time.sleep(2)

    window = MainWindow()
    window.show()
    
    # Finish splash screen
    splash.finish(window)
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()