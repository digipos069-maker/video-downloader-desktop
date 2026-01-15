import sys
import os
import time
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QVBoxLayout, QWidget, QSizeGrip, QSplashScreen
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QFont, QColor
from app.ui.downloader_tab import DownloaderTab, UpdateWorker
from app.ui.settings_tab import SettingsTab
from app.ui.widgets.title_bar import TitleBar
from app.ui.splash_screen import ModernSplashScreen
from app.config.settings_manager import save_settings
from app.helpers import resource_path, get_app_path

class MainWindow(QMainWindow):
    def __init__(self, initial_update_info=None):
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
        self.downloader_tab = DownloaderTab(initial_update_info=initial_update_info)
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
    
    # --- Show Modern Splash Screen ---
    splash = ModernSplashScreen()
    splash.show()
    app.processEvents()

    # --- Start Background Update Check ---
    update_result = {'info': None}
    
    # Create worker
    update_worker = UpdateWorker()
    
    # Define slot to capture result
    def on_update_checked(available, info):
        if available:
            update_result['info'] = info
            
    update_worker.finished.connect(on_update_checked)
    update_worker.start()

    # --- Initialization Steps ---
    
    # 1. Load Styles
    splash.update_progress(10, "Loading UI themes...")
    style_file = resource_path(os.path.join("app", "resources", "styles.qss"))
    if os.path.exists(style_file):
        with open(style_file, "r") as f:
            app.setStyleSheet(f.read())
    else:
        print(f"Warning: Stylesheet not found at {style_file}")
    
    # 2. Loading Steps + Update Wait
    steps = [
        (30, "Checking dependencies..."),
        (50, "Initializing platform handlers..."),
        (70, "Checking for updates..."), # Critical step
    ]
    
    for progress, msg in steps:
        time.sleep(0.2)
        splash.update_progress(progress, msg)
        app.processEvents()
        
    # Wait for update worker to finish (timeout 3 seconds to avoid hanging)
    wait_start = time.time()
    while update_worker.isRunning():
        if time.time() - wait_start > 3.0:
            update_worker.terminate() # Force stop if taking too long
            break
        app.processEvents()
        time.sleep(0.05)

    splash.update_progress(90, "Preparing interface...")
    time.sleep(0.2)
    splash.update_progress(100, "Starting...")
    time.sleep(0.2)

    # 3. Launch Main Window
    window = MainWindow(initial_update_info=update_result['info'])
    window.show()
    
    # Finish splash screen
    splash.finish(window)
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()