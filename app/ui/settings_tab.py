"""
The UI for the Settings tab.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QTabWidget, QHBoxLayout, 
    QCheckBox, QSpinBox, QComboBox, QLabel, QFormLayout, QPushButton, QMessageBox,
    QLineEdit, QFileDialog
)
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, Signal, Slot, QThread, QSize
import yt_dlp
import os
import sys
import tempfile
import json # for yt-dlp output parsing
import logging

from app.config.settings_manager import load_settings, save_settings
from app.config.credentials import CredentialsManager
from app.platform_handler import extract_metadata_with_playwright
from app.helpers import resource_path

# --- Styles ---
VERIFY_BTN_STYLE = """
    QPushButton {
        background-color: #3B82F6;
        color: white;
        border: none;
        padding: 6px 12px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 10pt;
        margin-top: 8px;
    }
    QPushButton:hover {
        background-color: #2563EB;
    }
    QPushButton:pressed {
        background-color: #1D4ED8;
    }
"""

SAVE_BTN_STYLE = """
    QPushButton {
        background-color: #3B82F6;
        color: white;
        border: none;
        padding: 6px 12px;
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

INPUT_STYLE = """
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

class CookieVerificationWorker(QThread):
    finished = Signal(bool, str)

    def __init__(self, cookie_file=None, browser_source=None, test_url=None, parent=None):
        super().__init__(parent)
        self.cookie_file = cookie_file
        self.browser_source = browser_source
        # Use provided test URL or default to Facebook (for backward compatibility if needed)
        self.test_url = test_url if test_url else "https://www.facebook.com/watch/?v=10153231379986729"

    def run(self):
        ydl_opts = {
            'quiet': True,
            'simulate': True, # Don't download
            'skip_download': True,
            'noplaylist': True,
            'ignoreerrors': True,
            'no_warnings': True,
            'dump_single_json': True,
        }

        logging.info(f"Starting cookie verification. File: '{self.cookie_file}', Browser: '{self.browser_source}'")

        if self.cookie_file:
            if os.path.exists(self.cookie_file):
                logging.info(f"Verifying with cookie file: {self.cookie_file}")
                ydl_opts['cookiefile'] = self.cookie_file
            else:
                msg = f"Cookie file path provided but file not found: {self.cookie_file}"
                logging.error(msg)
                self.finished.emit(False, msg)
                return
        elif self.browser_source and self.browser_source != "None":
            logging.info(f"Verifying with browser source: {self.browser_source}")
            ydl_opts['cookiesfrombrowser'] = (self.browser_source, )
        else:
            msg = "No cookie file or browser source provided."
            logging.error(msg)
            self.finished.emit(False, msg)
            return

        try:
            # Capture output using tempfile instead of pipe to avoid Windows buffering issues
            with tempfile.TemporaryFile(mode='w+', encoding='utf-8') as tmp_out, \
                 tempfile.TemporaryFile(mode='w+', encoding='utf-8') as tmp_err:
                
                original_stdout = sys.stdout
                original_stderr = sys.stderr
                
                try:
                    sys.stdout = tmp_out
                    sys.stderr = tmp_err
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.extract_info(self.test_url, download=False)
                except Exception:
                    # yt-dlp raises exceptions on failure even with ignoreerrors=True sometimes
                    pass
                finally:
                    sys.stdout = original_stdout # Restore stdout
                    sys.stderr = original_stderr # Restore stderr
                
                tmp_out.seek(0)
                output = tmp_out.read()
                
                tmp_err.seek(0)
                error_output = tmp_err.read()

            logging.debug(f"Verification Output: {output[:500]}...")
            if error_output:
                logging.error(f"Verification Stderr: {error_output}")
            
            # Check if JSON output indicates success
            if output.strip() and ('"id":' in output and '"title":' in output):
                self.finished.emit(True, "Cookies are valid! Accessed test video via yt-dlp.")
                return
            
            # --- FALLBACK: Playwright Verification ---
            # If yt-dlp failed (likely "Cannot parse data"), try Playwright to confirm accessibility
            logging.info("yt-dlp verification failed. Attempting Playwright fallback...")
            
            # We only try fallback if the error suggests parsing issues, not auth issues
            # But generally, if we can reach the site, it's 'Good Enough' for our Playwright-based scrapers
            
            pw_results = extract_metadata_with_playwright(self.test_url)
            if pw_results and pw_results[0].get('type') != 'error':
                # Check if we got valid-looking data (not just a login page title)
                first_res = pw_results[0]
                if "Login" in first_res.get('title', '') or "Log In" in first_res.get('title', ''):
                     self.finished.emit(False, "Verification failed: Page redirects to Login. Check cookies.")
                else:
                     self.finished.emit(True, "Verified via Browser (Playwright). yt-dlp parsing failed, but site is accessible.")
            else:
                # Use the original yt-dlp error if Playwright also fails
                if "Cannot parse data" in output or "Cannot parse data" in error_output:
                     self.finished.emit(False, "Verification failed: yt-dlp could not parse Facebook data. This is a known issue with recent Facebook updates.")
                elif "Login required" in output or "This video is private" in output:
                     self.finished.emit(False, "Verification failed: Cookies invalid or expired.")
                else:
                     clean_err = error_output.strip() if error_output else "Unknown error"
                     self.finished.emit(False, f"Verification failed. yt-dlp error: {clean_err[:300]}")

        except Exception as e:
            logging.error(f"Verification failed with exception: {e}")
            self.finished.emit(False, f"Verification failed with error: {e}")


class SettingsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.credentials_manager = CredentialsManager()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        label_style = "color: #A1A1AA; font-weight: 600; background-color: transparent;"
        
        self.setStyleSheet(INPUT_STYLE) # Apply globally

        # --- Global Settings ---
        global_settings_layout = QHBoxLayout()
        global_settings_layout.setSpacing(10)

        # 1. Video Settings Box
        video_group = QGroupBox("Video Settings")
        video_layout = QVBoxLayout()
        video_layout.setSpacing(8)

        self.enable_video_chk = QCheckBox("Enable Video Download")
        
        # Top Videos Row
        top_video_layout = QHBoxLayout()
        self.top_video_chk = QCheckBox("Top Videos")
        
        self.top_video_count = QSpinBox()
        self.top_video_count.setRange(1, 10000)
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
        photo_layout.setSpacing(8)

        self.enable_photo_chk = QCheckBox("Enable Photo Download")
        
        # Top Photos Row
        top_photo_layout = QHBoxLayout()
        self.top_photo_chk = QCheckBox("Top Photos")
        
        self.top_photo_count = QSpinBox()
        self.top_photo_count.setRange(1, 10000)
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
        self.credentials_tabs.setIconSize(QSize(20, 20))
        icon_base_path = resource_path("app/resources/images/icons/social/")
        
        # --- Facebook Credentials Tab ---
        facebook_tab = QWidget()
        fb_layout = QVBoxLayout(facebook_tab)
        fb_layout.setSpacing(8)
        fb_layout.setContentsMargins(10, 10, 10, 10)
        
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
        
        # --- Verify Cookies Button ---
        verify_btn_layout = QHBoxLayout()
        self.verify_fb_cookies_btn = QPushButton("Verify Cookies")
        self.verify_fb_cookies_btn.clicked.connect(self.verify_fb_cookies)
        self.verify_fb_cookies_btn.setStyleSheet(VERIFY_BTN_STYLE)
        verify_btn_layout.addStretch()
        verify_btn_layout.addWidget(self.verify_fb_cookies_btn)
        fb_layout.addLayout(verify_btn_layout)
        
        fb_layout.addStretch()
        self.credentials_tabs.addTab(facebook_tab, QIcon(icon_base_path + "facebook.png"), "Facebook")
        
        # --- Pinterest Credentials Tab ---
        pinterest_tab = QWidget()
        pin_layout = QVBoxLayout(pinterest_tab)
        pin_layout.setSpacing(8)
        pin_layout.setContentsMargins(10, 10, 10, 10)
        
        pin_desc = QLabel("Pinterest requires cookies for downloading high-res images and some videos.\nSelect your 'cookies.txt' or browser.")
        pin_desc.setStyleSheet("color: #A1A1AA; font-size: 9pt; margin-bottom: 10px;")
        pin_desc.setWordWrap(True)
        pin_layout.addWidget(pin_desc)
        
        # Pinterest Cookies File
        pin_cookies_layout = QHBoxLayout()
        self.pin_cookies_path = QLineEdit()
        self.pin_cookies_path.setPlaceholderText("Path to pinterest cookies.txt...")
        self.pin_cookies_btn = QPushButton("Browse...")
        self.pin_cookies_btn.clicked.connect(self.browse_pin_cookies)
        self.pin_cookies_btn.setStyleSheet("background-color: #27272A; color: #F4F4F5; border: 1px solid #3F3F46; border-radius: 6px; padding: 5px 10px;")
        
        pin_cookies_layout.addWidget(QLabel("Cookies File:"))
        pin_cookies_layout.addWidget(self.pin_cookies_path)
        pin_cookies_layout.addWidget(self.pin_cookies_btn)
        pin_layout.addLayout(pin_cookies_layout)

        # Pinterest Browser Option
        pin_browser_layout = QHBoxLayout()
        self.pin_browser_combo = QComboBox()
        self.pin_browser_combo.addItems(["None", "chrome", "firefox", "opera", "edge", "brave", "vivaldi"])
        
        pin_browser_layout.addWidget(QLabel("Browser Source:"))
        pin_browser_layout.addWidget(self.pin_browser_combo)
        pin_browser_layout.addStretch()
        pin_layout.addLayout(pin_browser_layout)
        
        # Verify Pinterest Button
        verify_pin_layout = QHBoxLayout()
        self.verify_pin_cookies_btn = QPushButton("Verify Cookies")
        self.verify_pin_cookies_btn.clicked.connect(self.verify_pin_cookies)
        self.verify_pin_cookies_btn.setStyleSheet(VERIFY_BTN_STYLE)
        verify_pin_layout.addStretch()
        verify_pin_layout.addWidget(self.verify_pin_cookies_btn)
        pin_layout.addLayout(verify_pin_layout)
        
        pin_layout.addStretch()
        self.credentials_tabs.addTab(pinterest_tab, QIcon(icon_base_path + "pinterest.png"), "Pinterest")

        # --- TikTok Credentials Tab ---
        tiktok_tab = QWidget()
        tt_layout = QVBoxLayout(tiktok_tab)
        tt_layout.setSpacing(8)
        tt_layout.setContentsMargins(10, 10, 10, 10)
        
        tt_desc = QLabel("TikTok generally works without cookies, but they help avoid CAPTCHAs and fetch more metadata.")
        tt_desc.setStyleSheet("color: #A1A1AA; font-size: 9pt; margin-bottom: 10px;")
        tt_desc.setWordWrap(True)
        tt_layout.addWidget(tt_desc)
        
        # TikTok Cookies File
        tt_cookies_layout = QHBoxLayout()
        self.tt_cookies_path = QLineEdit()
        self.tt_cookies_path.setPlaceholderText("Path to tiktok cookies.txt...")
        self.tt_cookies_btn = QPushButton("Browse...")
        self.tt_cookies_btn.clicked.connect(self.browse_tt_cookies)
        self.tt_cookies_btn.setStyleSheet("background-color: #27272A; color: #F4F4F5; border: 1px solid #3F3F46; border-radius: 6px; padding: 5px 10px;")
        
        tt_cookies_layout.addWidget(QLabel("Cookies File:"))
        tt_cookies_layout.addWidget(self.tt_cookies_path)
        tt_cookies_layout.addWidget(self.tt_cookies_btn)
        tt_layout.addLayout(tt_cookies_layout)

        # TikTok Browser Option
        tt_browser_layout = QHBoxLayout()
        self.tt_browser_combo = QComboBox()
        self.tt_browser_combo.addItems(["None", "chrome", "firefox", "opera", "edge", "brave", "vivaldi"])
        
        tt_browser_layout.addWidget(QLabel("Browser Source:"))
        tt_browser_layout.addWidget(self.tt_browser_combo)
        tt_browser_layout.addStretch()
        tt_layout.addLayout(tt_browser_layout)
        
        # Verify TikTok Button
        verify_tt_layout = QHBoxLayout()
        self.verify_tt_cookies_btn = QPushButton("Verify Cookies")
        self.verify_tt_cookies_btn.clicked.connect(self.verify_tt_cookies)
        self.verify_tt_cookies_btn.setStyleSheet(VERIFY_BTN_STYLE)
        verify_tt_layout.addStretch()
        verify_tt_layout.addWidget(self.verify_tt_cookies_btn)
        tt_layout.addLayout(verify_tt_layout)
        
        tt_layout.addStretch()
        self.credentials_tabs.addTab(tiktok_tab, QIcon(icon_base_path + "tik-tok.png"), "TikTok")
        
        # --- YouTube Credentials Tab ---
        youtube_tab = QWidget()
        yt_layout = QVBoxLayout(youtube_tab)
        yt_layout.setSpacing(8)
        yt_layout.setContentsMargins(10, 10, 10, 10)
        
        yt_desc = QLabel("YouTube cookies are often required for age-restricted content or premium videos.\nSelect your 'cookies.txt' or browser.")
        yt_desc.setStyleSheet("color: #A1A1AA; font-size: 9pt; margin-bottom: 10px;")
        yt_desc.setWordWrap(True)
        yt_layout.addWidget(yt_desc)
        
        # YouTube Cookies File
        yt_cookies_layout = QHBoxLayout()
        self.yt_cookies_path = QLineEdit()
        self.yt_cookies_path.setPlaceholderText("Path to youtube cookies.txt...")
        self.yt_cookies_btn = QPushButton("Browse...")
        self.yt_cookies_btn.clicked.connect(self.browse_yt_cookies)
        self.yt_cookies_btn.setStyleSheet("background-color: #27272A; color: #F4F4F5; border: 1px solid #3F3F46; border-radius: 6px; padding: 5px 10px;")
        
        yt_cookies_layout.addWidget(QLabel("Cookies File:"))
        yt_cookies_layout.addWidget(self.yt_cookies_path)
        yt_cookies_layout.addWidget(self.yt_cookies_btn)
        yt_layout.addLayout(yt_cookies_layout)

        # YouTube Browser Option
        yt_browser_layout = QHBoxLayout()
        self.yt_browser_combo = QComboBox()
        self.yt_browser_combo.addItems(["None", "chrome", "firefox", "opera", "edge", "brave", "vivaldi"])
        
        yt_browser_layout.addWidget(QLabel("Browser Source:"))
        yt_browser_layout.addWidget(self.yt_browser_combo)
        yt_browser_layout.addStretch()
        yt_layout.addLayout(yt_browser_layout)
        
        # Verify YouTube Button
        verify_yt_layout = QHBoxLayout()
        self.verify_yt_cookies_btn = QPushButton("Verify Cookies")
        self.verify_yt_cookies_btn.clicked.connect(self.verify_yt_cookies)
        self.verify_yt_cookies_btn.setStyleSheet(VERIFY_BTN_STYLE)
        verify_yt_layout.addStretch()
        verify_yt_layout.addWidget(self.verify_yt_cookies_btn)
        yt_layout.addLayout(verify_yt_layout)
        
        yt_layout.addStretch()
        self.credentials_tabs.addTab(youtube_tab, QIcon(icon_base_path + "youtube.png"), "YouTube")

        # Placeholder Tabs
        self.credentials_tabs.addTab(QWidget(), QIcon(icon_base_path + "instagram.png"), "Instagram")
        
        cred_layout.addWidget(self.credentials_tabs)
        credentials_group.setLayout(cred_layout)

        layout.addWidget(credentials_group)

        # Save Button
        save_btn = QPushButton("Save Settings")
        save_btn.setStyleSheet(SAVE_BTN_STYLE)
        save_btn.clicked.connect(self.save_current_settings)
        layout.addWidget(save_btn)
        
        layout.addStretch() # Pushes the group to the top
        
        # Load initial settings
        self.load_initial_settings()

    def browse_fb_cookies(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Cookies File", "", "Text Files (*.txt);;All Files (*)")
        if path:
            self.fb_cookies_path.setText(path)

    def browse_pin_cookies(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Pinterest Cookies File", "", "Text Files (*.txt);;All Files (*)")
        if path:
            self.pin_cookies_path.setText(path)

    def browse_tt_cookies(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select TikTok Cookies File", "", "Text Files (*.txt);;All Files (*)")
        if path:
            self.tt_cookies_path.setText(path)

    def browse_yt_cookies(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select YouTube Cookies File", "", "Text Files (*.txt);;All Files (*)")
        if path:
            self.yt_cookies_path.setText(path)

    @Slot()
    def verify_fb_cookies(self):
        cookie_file = self.fb_cookies_path.text()
        browser_source = self.fb_browser_combo.currentText()
        test_url = "https://www.facebook.com/watch/?v=10153231379986729" # FB Test URL
        self._verify_cookies(cookie_file, browser_source, test_url, self.verify_fb_cookies_btn)

    @Slot()
    def verify_pin_cookies(self):
        cookie_file = self.pin_cookies_path.text()
        browser_source = self.pin_browser_combo.currentText()
        test_url = "https://www.pinterest.com/" # Pinterest Test URL (Main page is usually sufficient for login check)
        self._verify_cookies(cookie_file, browser_source, test_url, self.verify_pin_cookies_btn)

    @Slot()
    def verify_tt_cookies(self):
        cookie_file = self.tt_cookies_path.text()
        browser_source = self.tt_browser_combo.currentText()
        test_url = "https://www.tiktok.com/@tiktok" # TikTok Test URL
        self._verify_cookies(cookie_file, browser_source, test_url, self.verify_tt_cookies_btn)

    @Slot()
    def verify_yt_cookies(self):
        cookie_file = self.yt_cookies_path.text()
        browser_source = self.yt_browser_combo.currentText()
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ" # YouTube Test URL (Rick Roll - always public, good for basic check)
        self._verify_cookies(cookie_file, browser_source, test_url, self.verify_yt_cookies_btn)

    def _verify_cookies(self, cookie_file, browser_source, test_url, btn_widget):
        if not cookie_file and (not browser_source or browser_source == "None"):
            QMessageBox.warning(self, "Verification Failed", "Please provide a cookie file or select a browser source.")
            return

        btn_widget.setEnabled(False)
        original_text = btn_widget.text()
        btn_widget.setText("Verifying...")
        
        # Store reference to button to restore it later
        self.active_verify_btn = btn_widget
        self.active_verify_btn_text = original_text

        self.cookie_worker = CookieVerificationWorker(cookie_file, browser_source, test_url, self)
        self.cookie_worker.finished.connect(self.on_cookie_verification_finished)
        self.cookie_worker.start()

    @Slot(bool, str)
    def on_cookie_verification_finished(self, success, message):
        if hasattr(self, 'active_verify_btn'):
            self.active_verify_btn.setEnabled(True)
            self.active_verify_btn.setText(self.active_verify_btn_text)

        if success:
            QMessageBox.information(self, "Verification Success", message)
        else:
            QMessageBox.critical(self, "Verification Failed", message)

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
            self._set_combo_text(self.fb_browser_combo, fb_creds.get('browser', 'None'))

        pin_creds = self.credentials_manager.get_credential('pinterest')
        if pin_creds:
            self.pin_cookies_path.setText(pin_creds.get('cookie_file', ''))
            self._set_combo_text(self.pin_browser_combo, pin_creds.get('browser', 'None'))

        tt_creds = self.credentials_manager.get_credential('tiktok')
        if tt_creds:
            self.tt_cookies_path.setText(tt_creds.get('cookie_file', ''))
            self._set_combo_text(self.tt_browser_combo, tt_creds.get('browser', 'None'))

        yt_creds = self.credentials_manager.get_credential('youtube')
        if yt_creds:
            self.yt_cookies_path.setText(yt_creds.get('cookie_file', ''))
            self._set_combo_text(self.yt_browser_combo, yt_creds.get('browser', 'None'))

    def _set_combo_text(self, combo, text):
        idx = combo.findText(text)
        if idx >= 0:
            combo.setCurrentIndex(idx)

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

        pin_data = {
            'cookie_file': self.pin_cookies_path.text(),
            'browser': self.pin_browser_combo.currentText()
        }
        self.credentials_manager.set_credential('pinterest', pin_data)

        tt_data = {
            'cookie_file': self.tt_cookies_path.text(),
            'browser': self.tt_browser_combo.currentText()
        }
        self.credentials_manager.set_credential('tiktok', tt_data)

        yt_data = {
            'cookie_file': self.yt_cookies_path.text(),
            'browser': self.yt_browser_combo.currentText()
        }
        self.credentials_manager.set_credential('youtube', yt_data)

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
