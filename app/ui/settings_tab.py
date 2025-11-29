"""
The UI for the Settings tab.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QTabWidget, QHBoxLayout, 
    QCheckBox, QSpinBox, QComboBox, QLabel, QFormLayout, QPushButton, QMessageBox,
    QLineEdit, QFileDialog
)
from PySide6.QtCore import Qt
from app.config.settings_manager import load_settings, save_settings
from app.config.credentials import CredentialsManager

class SettingsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.credentials_manager = CredentialsManager()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # --- Styles ---
        input_style = """
            QComboBox, QSpinBox {
                background-color: #1C1C21;
                border: 2px solid #27272A;
                border-radius: 8px;
                padding: 4px 8px;
                color: #F4F4F5;
                font-size: 10pt;
                min-width: 80px;
            }
            QComboBox:hover, QSpinBox:hover {
                border-color: #3B82F6;
                background-color: #202025;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QCheckBox {
                color: #F4F4F5;
                font-size: 10pt;
                background-color: transparent;
                spacing: 8px;
            }
            QCheckBox::indicator {
                border: 2px solid #3F3F46;
                border-radius: 4px;
                width: 18px;
                height: 18px;
                background: transparent;
            }
            QCheckBox::indicator:checked {
                background-color: #3B82F6;
                border-color: #3B82F6;
            }
            
            /* LineEdit for File Paths */
            QLineEdit {
                background-color: #1C1C21;
                border: 2px solid #27272A;
                border-radius: 8px;
                padding: 4px 8px;
                color: #F4F4F5;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border-color: #3B82F6;
                background-color: #202025;
            }
        """
        
        label_style = "color: #A1A1AA; font-weight: 600; background-color: transparent;"
        
        self.setStyleSheet(input_style) # Apply globally

        # --- Global Settings ---
        global_settings_layout = QHBoxLayout()
        global_settings_layout.setSpacing(20)

        # 1. Video Settings Box
        video_group = QGroupBox("Video Settings")
        video_layout = QVBoxLayout()
        video_layout.setSpacing(15)

        self.enable_video_chk = QCheckBox("Enable Video Download")
        
        # Top Videos Row
        top_video_layout = QHBoxLayout()
        self.top_video_chk = QCheckBox("Top Videos")
        
        self.top_video_count = QSpinBox()
        self.top_video_count.setRange(1, 100)
        self.top_video_count.setValue(5)
        
        top_video_layout.addWidget(self.top_video_chk)
        top_video_layout.addWidget(self.top_video_count)
        top_video_layout.addStretch()

        self.all_video_chk = QCheckBox("All Videos")
        
        # Resolution Row
        res_layout = QHBoxLayout()
        res_label = QLabel("Resolution:")
        res_label.setStyleSheet(label_style)
        
        self.video_res_combo = QComboBox()
        self.video_res_combo.addItems(["Best Available", "4K", "1080p", "720p", "480p", "360p"])
        
        res_layout.addWidget(res_label)
        res_layout.addWidget(self.video_res_combo)
        res_layout.addStretch()

        video_layout.addWidget(self.enable_video_chk)
        video_layout.addLayout(top_video_layout)
        video_layout.addWidget(self.all_video_chk)
        video_layout.addLayout(res_layout)
        video_layout.addStretch()
        video_group.setLayout(video_layout)

        # 2. Photo Settings Box
        photo_group = QGroupBox("Photo Settings")
        photo_layout = QVBoxLayout()
        photo_layout.setSpacing(15)

        self.enable_photo_chk = QCheckBox("Enable Photo Download")
        
        # Top Photos Row
        top_photo_layout = QHBoxLayout()
        self.top_photo_chk = QCheckBox("Top Photos")
        
        self.top_photo_count = QSpinBox()
        self.top_photo_count.setRange(1, 100)
        self.top_photo_count.setValue(5)
        
        top_photo_layout.addWidget(self.top_photo_chk)
        top_photo_layout.addWidget(self.top_photo_count)
        top_photo_layout.addStretch()

        self.all_photo_chk = QCheckBox("All Photos")
        
        # Resolution (Quality) Row
        photo_res_layout = QHBoxLayout()
        photo_res_label = QLabel("Quality:")
        photo_res_label.setStyleSheet(label_style)
        
        self.photo_res_combo = QComboBox()
        self.photo_res_combo.addItems(["Best Available", "High", "Medium", "Low"])
        
        photo_res_layout.addWidget(photo_res_label)
        photo_res_layout.addWidget(self.photo_res_combo)
        photo_res_layout.addStretch()

        photo_layout.addWidget(self.enable_photo_chk)
        photo_layout.addLayout(top_photo_layout)
        photo_layout.addWidget(self.all_photo_chk)
        photo_layout.addLayout(photo_res_layout)
        photo_layout.addStretch()
        photo_group.setLayout(photo_layout)

        # Add boxes to global layout
        global_settings_layout.addWidget(video_group)
        global_settings_layout.addWidget(photo_group)

        # Global Header
        global_header = QLabel("Global Settings")
        global_header.setStyleSheet("color: #3B82F6; font-size: 12pt; font-weight: bold; margin-bottom: 2px;")
        layout.addWidget(global_header)

        layout.addLayout(global_settings_layout)

        # Platform Credentials Header
        cred_header = QLabel("Platform Credentials")
        cred_header.setStyleSheet("color: #3B82F6; font-size: 12pt; font-weight: bold; margin-bottom: 2px; margin-top: 15px;")
        layout.addWidget(cred_header)

        credentials_group = QGroupBox()
        credentials_group.setStyleSheet("QGroupBox { margin-top: 0px; }")
        cred_layout = QVBoxLayout()
        
        self.credentials_tabs = QTabWidget()
        
        # --- Facebook Credentials Tab ---
        facebook_tab = QWidget()
        fb_layout = QVBoxLayout(facebook_tab)
        fb_layout.setSpacing(10)
        fb_layout.setContentsMargins(15, 15, 15, 15)
        
        fb_desc = QLabel("For private or age-restricted content, you must be logged in.\nOption 1 (Preferred): Select a 'cookies.txt' file exported from your browser (Netscape format).\nOption 2: Select the browser where you are already logged into Facebook.")
        fb_desc.setStyleSheet("color: #A1A1AA; font-size: 9pt; margin-bottom: 10px;")
        fb_desc.setWordWrap(True)
        fb_layout.addWidget(fb_desc)
        
        # Cookies File Option
        fb_cookies_layout = QHBoxLayout()
        self.fb_cookies_path = QLineEdit()
        self.fb_cookies_path.setPlaceholderText("Path to cookies.txt...")
        self.fb_cookies_btn = QPushButton("Browse...")
        self.fb_cookies_btn.clicked.connect(self.browse_fb_cookies)
        self.fb_cookies_btn.setStyleSheet("background-color: #27272A; color: #F4F4F5; border: 1px solid #3F3F46; border-radius: 6px; padding: 5px 10px;")
        
        fb_cookies_layout.addWidget(QLabel("Cookies File:"))
        fb_cookies_layout.addWidget(self.fb_cookies_path)
        fb_cookies_layout.addWidget(self.fb_cookies_btn)
        fb_layout.addLayout(fb_cookies_layout)

        # Browser Option
        fb_browser_layout = QHBoxLayout()
        self.fb_browser_combo = QComboBox()
        self.fb_browser_combo.addItems(["None", "chrome", "firefox", "opera", "edge", "brave", "vivaldi"])
        
        fb_browser_layout.addWidget(QLabel("Browser Source:"))
        fb_browser_layout.addWidget(self.fb_browser_combo)
        fb_browser_layout.addStretch()
        fb_layout.addLayout(fb_browser_layout)
        
        fb_layout.addStretch()
        self.credentials_tabs.addTab(facebook_tab, "Facebook")
        
        # Placeholder Tabs
        self.credentials_tabs.addTab(QWidget(), "Instagram")
        self.credentials_tabs.addTab(QWidget(), "YouTube")
        
        cred_layout.addWidget(self.credentials_tabs)
        credentials_group.setLayout(cred_layout)

        layout.addWidget(credentials_group)

        # Save Button
        save_btn = QPushButton("Save Settings")
        save_btn_style = """
            QPushButton {
                background-color: #3B82F6;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
            QPushButton:pressed {
                background-color: #1D4ED8;
            }
        """
        save_btn.setStyleSheet(save_btn_style)
        save_btn.clicked.connect(self.save_current_settings)
        layout.addWidget(save_btn)
        
        layout.addStretch() # Pushes the group to the top
        
        # Load initial settings
        self.load_initial_settings()

    def browse_fb_cookies(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Cookies File", "", "Text Files (*.txt);;All Files (*)")
        if path:
            self.fb_cookies_path.setText(path)

    def get_settings(self):
        """Returns the current global settings as a dictionary."""
        return {
            'video': {
                'enabled': self.enable_video_chk.isChecked(),
                'top': self.top_video_chk.isChecked(),
                'count': self.top_video_count.value(),
                'all': self.all_video_chk.isChecked(),
                'resolution': self.video_res_combo.currentText()
            },
            'photo': {
                'enabled': self.enable_photo_chk.isChecked(),
                'top': self.top_photo_chk.isChecked(),
                'count': self.top_photo_count.value(),
                'all': self.all_photo_chk.isChecked(),
                'quality': self.photo_res_combo.currentText()
            }
        }

    def set_settings(self, settings):
        """Updates the UI elements with the provided settings."""
        # Video Settings
        video_settings = settings.get('video', {})
        self.enable_video_chk.setChecked(video_settings.get('enabled', False))
        self.top_video_chk.setChecked(video_settings.get('top', False))
        self.top_video_count.setValue(video_settings.get('count', 5))
        self.all_video_chk.setChecked(video_settings.get('all', False))
        
        res_text = video_settings.get('resolution', "Best Available")
        index = self.video_res_combo.findText(res_text)
        if index >= 0:
            self.video_res_combo.setCurrentIndex(index)

        # Photo Settings
        photo_settings = settings.get('photo', {})
        self.enable_photo_chk.setChecked(photo_settings.get('enabled', False))
        self.top_photo_chk.setChecked(photo_settings.get('top', False))
        self.top_photo_count.setValue(photo_settings.get('count', 5))
        self.all_photo_chk.setChecked(photo_settings.get('all', False))
        
        qual_text = photo_settings.get('quality', "Best Available")
        index = self.photo_res_combo.findText(qual_text)
        if index >= 0:
            self.photo_res_combo.setCurrentIndex(index)

        # Load Credentials
        fb_creds = self.credentials_manager.get_credential('facebook')
        if fb_creds:
            self.fb_cookies_path.setText(fb_creds.get('cookie_file', ''))
            browser = fb_creds.get('browser', 'None')
            idx = self.fb_browser_combo.findText(browser)
            if idx >= 0:
                self.fb_browser_combo.setCurrentIndex(idx)

    def load_initial_settings(self):
        """Loads settings from disk and populates the UI."""
        settings = load_settings()
        self.set_settings(settings)

    def save_current_settings(self):
        """Saves the current UI state to disk."""
        # Save General Settings
        settings = self.get_settings()
        success = save_settings(settings)
        
        # Save Credentials
        fb_data = {
            'cookie_file': self.fb_cookies_path.text(),
            'browser': self.fb_browser_combo.currentText()
        }
        self.credentials_manager.set_credential('facebook', fb_data)

        if success:
            QMessageBox.information(self, "Success", "Settings and Credentials saved successfully!")
        else:
            QMessageBox.critical(self, "Error", "Failed to save settings.")

if __name__ == '__main__':
    import sys, os
    from PySide6.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)
    
    # Applying the stylesheet for standalone testing
    style_file = os.path.join(os.path.dirname(__file__), "..", "resources", "styles.qss")
    if os.path.exists(style_file):
        with open(style_file, "r") as f:
            app.setStyleSheet(f.read())

    window = QMainWindow()
    settings_tab = SettingsTab()
    window.setCentralWidget(settings_tab)
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec())
