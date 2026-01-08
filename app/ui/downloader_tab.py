"""
The main UI for the downloader tab.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QGroupBox, QTabWidget, QAbstractItemView,
    QHeaderView, QSizePolicy, QMessageBox, QSpacerItem, QTableWidgetItem,
    QFileDialog, QComboBox, QFormLayout, QCheckBox, QSpinBox, QFrame, QProgressBar,
    QSplitter
)
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QThread, QSize
import os

from app.platform_handler import PlatformHandlerFactory
from app.downloader import Downloader
from app.network import NetworkMonitor
from app.config.settings_manager import load_settings
from app.config.credentials import CredentialsManager
from app.config.license_manager import LicenseManager
from app.config.version import VERSION
from app.ui.license_dialog import LicenseDialog
from app.ui.edit_username_dialog import EditUsernameDialog
from app.ui.widgets.custom_message_box import CustomMessageBox
from app.ui.widgets.social_icon import SocialIcon
from app.helpers import resource_path, check_for_updates

class UpdateWorker(QThread):
    finished = Signal(bool, dict)

    def run(self):
        available, info = check_for_updates()
        self.finished.emit(available, info if info else {})

class ScrapingWorker(QThread):
    item_found = Signal(str, dict, bool, bool, object) # item_url, metadata, is_video, is_photo, handler
    finished = Signal()
    error = Signal(str)
    status_update = Signal(str) # New signal for status messages


    def __init__(self, url, handler_factory, settings, parent=None):
        super().__init__(parent)
        self.url = url
        self.handler_factory = handler_factory
        self.settings = settings

    def run(self):
        try:
            handler = self.handler_factory.get_handler(self.url)
            if not handler:
                self.error.emit(f"No handler found for URL: {self.url}")
                return

            video_opts = self.settings.get('video', {})
            photo_opts = self.settings.get('photo', {})
            
            video_enabled = video_opts.get('enabled', False)
            photo_enabled = photo_opts.get('enabled', False)
            
            limit_video = video_enabled and video_opts.get('top', False) and not video_opts.get('all', False)
            limit_photo = photo_enabled and photo_opts.get('top', False) and not photo_opts.get('all', False)
            
            target_count = 0
            if limit_video:
                target_count = max(target_count, video_opts.get('count', 5))
            if limit_photo:
                target_count = max(target_count, photo_opts.get('count', 5))
            
            fetch_limit = 100 # Default
            if video_opts.get('all', False) or photo_opts.get('all', False):
                 fetch_limit = 2000 # Increased limit for 'all'
            elif target_count > 0:
                 fetch_limit = target_count + 5 # Fetch a few more than target just in case of filters
            
            print(f"--- DEBUG SETTINGS ---")
            print(f"Video Enabled: {video_enabled}, Top: {video_opts.get('top')}, Count: {video_opts.get('count')}, All: {video_opts.get('all')}")
            print(f"Photo Enabled: {photo_enabled}, Top: {photo_opts.get('top')}, Count: {photo_opts.get('count')}, All: {photo_opts.get('all')}")
            print(f"Calculated Target Count: {target_count}")
            print(f"Final Fetch Limit: {fetch_limit}")
            print(f"----------------------")

            # State for callback
            state = {
                'video_count': 0,
                'photo_count': 0,
                'filtered_count': 0,
                'items_found_total': 0
            }

            def on_item_found_callback(metadata):
                state['items_found_total'] += 1
                try:
                    item_url = metadata['url']
                    print(f"[DEBUG] Processing URL: {item_url}")
                    
                    is_video = item_url.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm'))
                    is_photo = item_url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))
                    
                    if not is_video and not is_photo:
                        if any(x in item_url for x in ['youtube', 'youtu.be', 'tiktok', 'facebook']):
                            is_video = True
                        elif 'instagram' in item_url:
                            if any(x in item_url for x in ['/reel/', '/reels/', '/tv/']):
                                is_video = True
                            else:
                                is_photo = True # Assume anything else on Instagram is a post/photo
                        elif 'pinterest' in item_url:
                            is_hint_video = metadata.get('is_video_hint', False)
                            if is_hint_video:
                                is_video = True
                                is_photo = False
                            else:
                                # Default Pinterest links to photo if no video hint,
                                # unless only video download is enabled.
                                if photo_enabled:
                                    is_photo = True
                                    is_video = False
                                elif video_enabled:
                                    is_video = True
                                    is_photo = False
                    
                    print(f"[DEBUG] Initial Classification - is_video: {is_video}, is_photo: {is_photo}")
                    print(f"[DEBUG] Config - video_enabled: {video_enabled}, photo_enabled: {photo_enabled}, limit_photo: {limit_photo}")

                    # Apply Filters - Robust Logic for Dual Types
                    passed_video = False
                    passed_photo = False
                    
                    if is_video:
                        if video_enabled:
                            if not limit_video or state['video_count'] < video_opts.get('count', 5):
                                passed_video = True
                    
                    if is_photo:
                        if photo_enabled:
                            if not limit_photo or state['photo_count'] < photo_opts.get('count', 5):
                                passed_photo = True
                    
                    print(f"[DEBUG] Filter Result - passed_video: {passed_video}, passed_photo: {passed_photo}")

                    if not passed_video and not passed_photo:
                        state['filtered_count'] += 1
                        print(f"[DEBUG] Item FILTERED OUT: {item_url}")
                        return
                    
                    if passed_video: state['video_count'] += 1
                    if passed_photo: state['photo_count'] += 1
                    
                    # Update types to reflect what actually passed
                    is_video = passed_video
                    is_photo = passed_photo

                    metadata['origin_url'] = self.url
                    print(f"[DEBUG] EMITTING item_found for: {item_url}")
                    self.item_found.emit(item_url, metadata, is_video, is_photo, handler)
                    self.status_update.emit(f"Found {state['items_found_total']} items...")

                except Exception as loop_error:
                    print(f"[ERROR] Callback failed for item {metadata}: {loop_error}")

            metadata_list = handler.get_playlist_metadata(self.url, max_entries=fetch_limit, settings=self.settings, callback=on_item_found_callback)
            
            if not metadata_list and state['items_found_total'] == 0:
                self.error.emit(f"No downloadable items found for {self.url}.")
                return

            print(f"[DEBUG] Total items scraped: {state['items_found_total']}")
            
        except Exception as e:
            self.error.emit(f"Error scraping {self.url}: {e}")
        finally:
            self.finished.emit()

class DownloaderTab(QWidget):
    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.settings_tab = None # Reference to settings tab

        # --- Backend Setup ---
        self.platform_handler_factory = PlatformHandlerFactory()
        self.downloader = Downloader(self.platform_handler_factory)
        self.credentials_manager = CredentialsManager()
        self.license_manager = LicenseManager() # Initialize License Manager
        
        self.video_download_path = None
        self.photo_download_path = None

        # Connect signals from downloader to UI updates
        self.downloader.status.connect(self.update_download_status)
        self.downloader.progress.connect(self.update_download_progress)
        self.downloader.finished.connect(self.download_finished_callback)
        # Removed automatic queue display updates to keep scraped items out of the manual queue
        # self.downloader.download_started.connect(self.add_to_queue_display)
        # self.downloader.download_removed.connect(self.remove_from_queue_display)

        # --- Data mapping for UI updates ---
        self.active_download_map = {} # Maps item_id to its row in the queue_table_widget
        
        # --- Timer Setup ---
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timer_display)
        self.seconds_elapsed = 0
        
        # --- Progress Tracking ---
        self.total_downloads = 0
        self.completed_downloads = 0
        self.failed_downloads = 0 # Initialize failed downloads counter
        self.active_progress_bars = {} # item_id -> QProgressBar widget

        # --- Network Monitor Setup ---
        self.network_monitor = NetworkMonitor(self)
        self.network_monitor.stats_signal.connect(self.update_network_stats)
        self.network_monitor.start()

        # --- UI Layout ---
        main_layout = QVBoxLayout(self) # Changed to QVBoxLayout
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- Top Bar (Two Rows) ---
        top_bar_layout = QVBoxLayout()
        top_bar_layout.setSpacing(5)

        # Row 1: Logo, Network Speed, User
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(10)

        self.logo_label = QLabel() 
        self.logo_label.setFixedSize(48, 48)
        logo_pixmap = QPixmap(resource_path("app/resources/images/logo.png"))
        if not logo_pixmap.isNull():
            self.logo_label.setPixmap(logo_pixmap.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.logo_label.setText("SDM")
            self.logo_label.setAlignment(Qt.AlignCenter)
            self.logo_label.setStyleSheet("background-color: #383e48; border-radius: 24px; font-weight: bold; color: white;")
        
        # Speed Info Box
        speed_box = QFrame()
        speed_box.setFixedHeight(30)
        speed_box.setStyleSheet("""
            QFrame {
                background-color: #1C1C21;
                border: 1px solid #27272A;
                border-radius: 8px;
            }
            QLabel {
                border: none;
                background-color: transparent;
                color: #10B981; 
                font-weight: bold; 
                font-size: 9pt;
            }
        """)
        speed_layout = QHBoxLayout(speed_box)
        speed_layout.setContentsMargins(8, 0, 8, 0)
        self.speed_label = QLabel("↓ 0.00 Mbps / ↑ 0.00 Mbps")
        self.speed_label.setObjectName("speed_label")
        speed_layout.addWidget(self.speed_label)

        # User Info Box
        user_box = QFrame()
        user_box.setFixedHeight(30)
        user_box.setStyleSheet("""
            QFrame {
                background-color: #1C1C21;
                border: 1px solid #27272A;
                border-radius: 8px;
            }
            QLabel {
                border: none;
                background-color: transparent;
                color: #9CA3AF; 
                font-size: 9pt; 
                font-weight: 500;
            }
        """)
        user_layout = QHBoxLayout(user_box)
        user_layout.setContentsMargins(8, 0, 8, 0)
        self.username_label = QLabel("User: Guest")
        self.username_label.setObjectName("username_label")
        self.username_label.setCursor(Qt.PointingHandCursor)
        self.username_label.mousePressEvent = self.edit_username_event
        user_layout.addWidget(self.username_label)
        
        # Add widgets to row layout
        row1_layout.addWidget(self.logo_label)
        row1_layout.addWidget(speed_box)
        row1_layout.addWidget(user_box)
        
        # Timer Box Display
        self.timer_label = QLabel("00:00:00")
        self.timer_label.setAlignment(Qt.AlignCenter)
        self.timer_label.setFixedSize(90, 30)
        self.timer_label.setStyleSheet("""
            QLabel {
                background-color: #1C1C21;
                border: 1px solid #27272A;
                border-radius: 8px;
                color: #10B981; /* Green for timer */
                font-weight: bold;
                font-size: 10pt;
                font-family: Consolas, "Courier New", monospace;
            }
        """)
        row1_layout.addWidget(self.timer_label)
        
        row1_layout.addStretch()
        
        # Top Right Buttons (Update & License)
        self.check_update_button = QPushButton(" Check Update")
        self.check_update_button.setIcon(QIcon(resource_path("app/resources/images/icons/update_checked.png")))
        self.check_update_button.setIconSize(QSize(16, 16))
        self.check_update_button.setCursor(Qt.PointingHandCursor)
        self.check_update_button.setFixedHeight(26)
        self.check_update_button.clicked.connect(self.run_update_check)
        self.check_update_button.setStyleSheet("""
            QPushButton {
                background-color: #1C1C21;
                color: #A1A1AA;
                border: 1px solid #27272A;
                border-radius: 13px;
                padding: 0 10px;
                font-size: 9pt;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #27272A;
                color: #F4F4F5;
                border-color: #3B82F6;
            }
        """)
        
        self.license_status_button = QPushButton("License Status")
        self.license_status_button.setCursor(Qt.PointingHandCursor)
        self.license_status_button.setFixedHeight(30)
        self.license_status_button.setStyleSheet("""
            QPushButton {
                background-color: #1C1C21;
                color: #F59E0B;
                border: 1px solid #27272A;
                border-radius: 15px;
                padding: 0 10px;
                font-size: 9pt;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #27272A;
                border-color: #F59E0B;
            }
        """)
        self.license_status_button.clicked.connect(self.open_license_dialog)
        self.update_license_ui() # Set initial state
        
        row1_layout.addWidget(self.check_update_button)
        row1_layout.addWidget(self.license_status_button)
        
        top_bar_layout.addLayout(row1_layout)

        # Row 2: Input, Buttons, Supported Icons
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(5) 
        
        input_block_layout = QHBoxLayout()
        input_block_layout.setSpacing(5)
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste video URL here...")
        self.url_input.setFixedHeight(30)
        self.url_input.textChanged.connect(self.validate_url_input)
        self.url_input.setStyleSheet("""
            QLineEdit {
                background-color: #1C1C21;
                border: 2px solid #27272A;
                border-radius: 15px; /* approx 50% of 30px */
                padding: 0 8px;
                color: #F4F4F5;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border-color: #3B82F6;
                background-color: #202025;
            }
        """) 
        
        self.add_to_queue_button = QPushButton("Add to Queue")
        self.add_to_queue_button.setCursor(Qt.PointingHandCursor)
        self.add_to_queue_button.setFixedHeight(30)
        self.add_to_queue_button.clicked.connect(self.add_url_to_download_queue)
        self.add_to_queue_button.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: white;
                border-radius: 15px;
                padding: 0 10px;
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
            QPushButton:pressed {
                background-color: #1D4ED8;
            }
        """)
        
        self.scrap_button = QPushButton("Scrap Now")
        self.scrap_button.setCursor(Qt.PointingHandCursor)
        self.scrap_button.setFixedHeight(30)
        self.scrap_button.clicked.connect(self.scrap_url)
        self.scrap_button.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: white;
                border-radius: 15px;
                padding: 0 10px;
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #059669;
            }
            QPushButton:pressed {
                background-color: #047857;
            }
        """)
        
        input_block_layout.addWidget(self.url_input, 1) # Assign stretch factor 1 to make it expand
        input_block_layout.addWidget(self.add_to_queue_button)
        input_block_layout.addWidget(self.scrap_button)
        
        row2_layout.addLayout(input_block_layout)
        row2_layout.addStretch()
        
        # Supported Platform Icons
        platform_icons_layout = QHBoxLayout()
        platform_icons_layout.setSpacing(8) # Spacing between icons
        platform_icons_layout.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Base path for icons
        # Use os.path.join for cross-platform safety and remove trailing slash for cleaner joining later
        icon_base_path = resource_path(os.path.join("app", "resources", "images", "icons", "social"))

        # Add icons using the new SocialIcon widget with animation
        # Use os.path.join to construct full paths
        platform_icons_layout.addWidget(SocialIcon(os.path.join(icon_base_path, "youtube.png"), "YouTube", size=32))
        platform_icons_layout.addWidget(SocialIcon(os.path.join(icon_base_path, "tik-tok.png"), "TikTok", size=32))
        platform_icons_layout.addWidget(SocialIcon(os.path.join(icon_base_path, "facebook.png"), "Facebook", size=32))
        platform_icons_layout.addWidget(SocialIcon(os.path.join(icon_base_path, "instagram.png"), "Instagram", size=32))
        platform_icons_layout.addWidget(SocialIcon(os.path.join(icon_base_path, "pinterest.png"), "Pinterest", size=32))
        
        row2_layout.addLayout(platform_icons_layout)
        
        top_bar_layout.addLayout(row2_layout)

        # --- Content Area (Two Columns with Splitter) ---
        self.content_splitter = QSplitter(Qt.Horizontal)
        self.content_splitter.setHandleWidth(8)
        self.content_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #101014;
            }
            QSplitter::handle:hover {
                background-color: #3B82F6;
            }
        """)

        # --- Left Sidebar ---
        left_sidebar_widget = QWidget()
        left_sidebar_layout = QVBoxLayout(left_sidebar_widget)
        left_sidebar_layout.setContentsMargins(0, 0, 0, 0)
        left_sidebar_layout.setSpacing(8)
        # left_sidebar_widget.setFixedWidth(240) # Removed fixed width

        # --- Right Side (Main Content) ---
        right_content_widget = QWidget() # Container for right side
        right_content_layout = QVBoxLayout(right_content_widget)
        right_content_layout.setContentsMargins(0, 0, 0, 0) # Adjust margins if needed
        right_content_layout.setSpacing(8)
        
        # --- Left Sidebar Widgets ---
        queue_group = QGroupBox("URL Queue")
        queue_layout = QVBoxLayout()
        self.queue_table_widget = QTableWidget()
        self.queue_table_widget.setMinimumHeight(150) # Increased height
        self.queue_table_widget.setColumnCount(2)
        self.queue_table_widget.setHorizontalHeaderLabels(["#", "URL"])
        self.queue_table_widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents) # For '#' column
        self.queue_table_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch) # For 'URL' column
        self.queue_table_widget.verticalHeader().setVisible(False) # Hide default vertical row numbers
        self.queue_table_widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.queue_table_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.queue_table_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.queue_table_widget.customContextMenuRequested.connect(self.open_queue_context_menu)
        queue_layout.addWidget(self.queue_table_widget)
        queue_group.setLayout(queue_layout)
        
        paths_group = QGroupBox("Download Paths")
        paths_layout = QVBoxLayout()
        paths_layout.setSpacing(8)
        
        path_btn_style = """
            QPushButton {
                background-color: #1C1C21;
                color: #A1A1AA;
                border: 1px solid #27272A;
                border-radius: 8px;
                padding: 4px;
                text-align: left;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #27272A;
                color: #F4F4F5;
                border-color: #3B82F6;
            }
        """
        
        self.video_path_button = QPushButton("📁 Video Path...")
        self.video_path_button.setCursor(Qt.PointingHandCursor)
        self.video_path_button.setStyleSheet(path_btn_style)
        self.video_path_button.clicked.connect(self.select_video_path)
        
        self.photo_path_button = QPushButton("📁 Photo Path...")
        self.photo_path_button.setCursor(Qt.PointingHandCursor)
        self.photo_path_button.setStyleSheet(path_btn_style)
        self.photo_path_button.clicked.connect(self.select_photo_path)
        
        paths_layout.addWidget(self.video_path_button)
        paths_layout.addWidget(self.photo_path_button)
        paths_group.setLayout(paths_layout)

        left_sidebar_layout.addWidget(queue_group, 1) # Stretch factor 1 to fill space
        left_sidebar_layout.addWidget(paths_group)
        left_sidebar_layout.addSpacing(35) # Spacer to align bottom of Queue with Activity
        
        # --- Right Content Widgets ---
        activity_group = QGroupBox("Download Activity")
        activity_layout = QVBoxLayout()
        activity_layout.setContentsMargins(0, 5, 0, 0) 

        # Activity Table
        self.activity_table = QTableWidget()
        self.activity_table.setMinimumHeight(200) # Increased height
        self.activity_table.setColumnCount(9)
        self.activity_table.setHorizontalHeaderLabels(["#", "Title", "URL", "Status", "Type", "Platform", "ETA", "Size", "Progress"])
        self.activity_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents) # For '#' column
        for i in range(1, 9):
            self.activity_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Interactive)
        self.activity_table.horizontalHeader().setStretchLastSection(True) # Ensure table fills available width
        self.activity_table.verticalHeader().setVisible(False)
        self.activity_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.activity_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.activity_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.activity_table.customContextMenuRequested.connect(self.open_activity_context_menu)
        
        self.activity_row_map = {} # Maps item_id to row index
        
        activity_layout.addWidget(self.activity_table)
        activity_group.setLayout(activity_layout)

        
        # Bottom Section for Settings
        bottom_controls_layout = QHBoxLayout()
        settings_group = QGroupBox("Download Options")
        
        # Use a Horizontal layout for the settings group to place items side-by-side
        settings_layout = QHBoxLayout()
        settings_layout.setSpacing(10)
        
        # Define a modern stylesheet for the combo boxes and checkbox
        input_style = """
            QComboBox, QSpinBox {
                background-color: #1C1C21;
                border: 2px solid #27272A;
                border-radius: 8px;
                padding: 2px 6px;
                color: #F4F4F5;
                font-family: "Segoe UI", sans-serif;
                font-size: 10pt;
                min-width: 110px;
            }
            QComboBox:hover, QSpinBox:hover {
                border-color: #3B82F6;
                background-color: #202025;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 25px;
                border-left-width: 0px;
            }
            QComboBox::down-arrow {
                image: none; 
                border-left: 2px solid #F4F4F5;
                border-bottom: 2px solid #F4F4F5;
                width: 8px; 
                height: 8px;
                transform: rotate(-45deg);
                margin-top: -3px;
                margin-left: 2px;
            }
            QComboBox QAbstractItemView {
                background-color: #1C1C21;
                border: 1px solid #27272A;
                selection-background-color: #3B82F6;
                selection-color: #FFFFFF;
                outline: none;
                padding: 4px;
            }
            
            /* Modern Checkbox Style */
            QCheckBox {
                color: #F4F4F5;
                font-size: 10pt;
                font-weight: 500;
                spacing: 10px;
                background-color: transparent;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #3F3F46;
                border-radius: 6px;
                background-color: transparent;
            }
            QCheckBox::indicator:checked {
                background-color: #3B82F6;
                border-color: #3B82F6;
            }
            QCheckBox::indicator:hover {
                border-color: #60A5FA;
            }
        """
        
        # New distinct style for section headers (Labels)
        label_style = """
            color: #A1A1AA;
            background-color: transparent;
            font-weight: 700;
            font-size: 8pt;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 6px;
        """

        # Extension Section (User's "File Type")
        ext_layout = QVBoxLayout()
        ext_layout.setSpacing(4)
        ext_label = QLabel("Extension")
        ext_label.setStyleSheet(label_style)
        self.extension_combo = QComboBox()
        self.extension_combo.addItems(["Best", "mp4", "mp3", "mkv", "wav", "jpg", "png"])
        self.extension_combo.setCursor(Qt.PointingHandCursor)
        self.extension_combo.setStyleSheet(input_style)
        ext_layout.addWidget(ext_label)
        ext_layout.addWidget(self.extension_combo)
        ext_layout.addStretch()
        
        # Naming Style Section (User's "Video Format")
        naming_layout = QVBoxLayout()
        naming_layout.setSpacing(4)
        naming_label = QLabel("Naming Style")
        naming_label.setStyleSheet(label_style)
        self.naming_combo = QComboBox()
        self.naming_combo.addItems(["Original Name", "Numbered (01. Name)", "Video + Caption (.txt)"])
        self.naming_combo.setCursor(Qt.PointingHandCursor)
        self.naming_combo.setStyleSheet(input_style)
        naming_layout.addWidget(naming_label)
        naming_layout.addWidget(self.naming_combo)
        naming_layout.addStretch()
        
        # Extra Options Section
        options_layout = QVBoxLayout()
        options_layout.setSpacing(4)
        options_label = QLabel("Extras")
        options_label.setStyleSheet(label_style)
        self.subs_checkbox = QCheckBox("Download Subtitles")
        self.subs_checkbox.setCursor(Qt.PointingHandCursor)
        self.subs_checkbox.setStyleSheet(input_style)
        options_layout.addWidget(options_label)
        options_layout.addWidget(self.subs_checkbox)
        options_layout.addStretch()

        settings_layout.addLayout(ext_layout)
        settings_layout.addLayout(naming_layout)
        settings_layout.addLayout(options_layout)
        settings_layout.addStretch() 
        
        settings_group.setLayout(settings_layout)
        
        # --- System Settings Group ---
        system_group = QGroupBox("System Settings")
        system_layout = QVBoxLayout()
        system_layout.setSpacing(8)
        
        # Threads Option
        threads_layout = QHBoxLayout()
        threads_label = QLabel("Threads:")
        threads_label.setStyleSheet("color: #F4F4F5; font-weight: 500; background-color: transparent;")
        self.threads_spinbox = QSpinBox()
        import multiprocessing
        max_threads = multiprocessing.cpu_count()
        self.threads_spinbox.setRange(1, max_threads)
        self.threads_spinbox.setValue(max(1, int(max_threads / 2))) # Default to half max
        self.threads_spinbox.setSuffix(" Threads")
        self.threads_spinbox.setStyleSheet(input_style)
        self.threads_spinbox.setToolTip(f"Max detected threads: {max_threads}")
        self.threads_spinbox.valueChanged.connect(self.update_thread_count)
        
        threads_layout.addWidget(threads_label)
        threads_layout.addWidget(self.threads_spinbox)
        
        # Shutdown Option
        self.shutdown_checkbox = QCheckBox("Shutdown when finished")
        self.shutdown_checkbox.setCursor(Qt.PointingHandCursor)
        self.shutdown_checkbox.setStyleSheet(input_style)
        
        system_layout.addLayout(threads_layout)
        system_layout.addWidget(self.shutdown_checkbox)
        system_layout.addStretch()
        system_group.setLayout(system_layout)

        bottom_controls_layout.addWidget(settings_group)
        bottom_controls_layout.addWidget(system_group) # Add System Settings next to Download Options
        bottom_controls_layout.addStretch()

        # --- Footer Area ---
        footer_main_layout = QVBoxLayout()
        
        # Remove dynamic active downloads container
        # self.active_downloads_container = QWidget() ...

        # Footer Controls
        footer_layout = QHBoxLayout()
        
        # Global Status Label (For Scraping/Idle messages)
        self.global_status_label = QLabel("Ready")
        self.global_status_label.setAlignment(Qt.AlignCenter)
        self.global_status_label.setFixedHeight(20)
        self.global_status_label.setStyleSheet("""
            color: #3B82F6;
            font-weight: bold;
            font-size: 9pt;
        """)
        
        # Replaced Label with Global Progress Bar (For active downloads)
        self.global_progress_bar = QProgressBar()
        self.global_progress_bar.setRange(0, 1) # Default range
        self.global_progress_bar.setValue(0)
        self.global_progress_bar.setTextVisible(True)
        self.global_progress_bar.setFormat("Ready") # Initial text
        self.global_progress_bar.setFixedHeight(20)
        self.global_progress_bar.setVisible(False) # Hidden by default
        self.global_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #27272A;
                border-radius: 10px;
                text-align: center;
                color: #F4F4F5;
                background-color: #1C1C21;
                font-weight: bold;
                font-size: 10pt;
            }
            QProgressBar::chunk {
                background-color: #3B82F6;
                border-radius: 9px;
            }
        """)
        
        self.status_message.connect(self.handle_status_message)
        
        action_btn_style = """
             QPushButton {
                border-radius: 15px; /* 50% of 30px height */
                padding: 0 12px;
                font-weight: bold;
                font-size: 11pt;
            }
        """
        
        self.download_button = QPushButton("Download All")
        self.download_button.setCursor(Qt.PointingHandCursor)
        self.download_button.setFixedHeight(30)
        self.download_button.clicked.connect(self.start_download_from_queue)
        self.download_button.setStyleSheet(action_btn_style + """
            QPushButton {
                background-color: #3B82F6;
                color: white;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
            QPushButton:pressed {
                background-color: #1D4ED8;
            }
        """)
        
        self.cancel_button = QPushButton("Cancel All")
        self.cancel_button.setCursor(Qt.PointingHandCursor)
        self.cancel_button.setFixedHeight(30)
        self.cancel_button.clicked.connect(self.cancel_all_downloads) # Connected to new slot
        self.cancel_button.setStyleSheet(action_btn_style + """
             QPushButton {
                background-color: #EF4444;
                color: white;
            }
            QPushButton:hover {
                background-color: #DC2626;
            }
            QPushButton:pressed {
                background-color: #B91C1C;
            }
        """)
        
        footer_layout.addWidget(self.global_status_label, 1)
        footer_layout.addWidget(self.global_progress_bar, 1) # Give it stretch 1 to expand
        footer_layout.addSpacing(8)
        footer_layout.addWidget(self.download_button)
        footer_layout.addWidget(self.cancel_button)
        
        footer_main_layout.addLayout(footer_layout)

        # --- Assemble Right Layout ---
        right_content_layout.addWidget(activity_group, 1) # STRETCH FACTOR 1 - THIS MAKES IT EXPAND
        right_content_layout.addLayout(bottom_controls_layout)
        right_content_layout.addLayout(footer_main_layout)
        
        # --- Assemble Content Splitter ---
        self.content_splitter.addWidget(left_sidebar_widget)
        self.content_splitter.addWidget(right_content_widget)
        
        # Set initial sizes (Sidebar 180px, Rest to content)
        self.content_splitter.setSizes([180, 800])
        self.content_splitter.setCollapsible(0, False) # Prevent sidebar from collapsing completely
        self.content_splitter.setCollapsible(1, False) # Prevent content from collapsing completely

        # --- Assemble Main Layout ---
        main_layout.addLayout(top_bar_layout)
        main_layout.addWidget(self.content_splitter, 1) # Add stretch factor 1 to fill remaining vertical space

        # Load initial UI state
        self.load_ui_state()

    @Slot()
    def run_update_check(self):
        self.check_update_button.setEnabled(False)
        self.check_update_button.setText(" Checking...")
        
        self.update_thread = UpdateWorker(self)
        self.update_thread.finished.connect(self.on_update_check_finished)
        self.update_thread.start()

    @Slot(bool, dict)
    def on_update_check_finished(self, available, info):
        self.check_update_button.setEnabled(True)
        self.check_update_button.setText(" Check Update")
        
        if available:
            new_version = info.get("version", "Unknown")
            notes = info.get("release_notes", "No notes available.")
            url = info.get("download_url", "")
            
            msg = f"A new version (v{new_version}) is available!\n\nRelease Notes:\n{notes}\n\nWould you like to go to the download page?"
            reply = QMessageBox.question(self, "Update Available", msg, QMessageBox.Yes | QMessageBox.No)
            
            if reply == QMessageBox.Yes and url:
                import webbrowser
                webbrowser.open(url)
        else:
            QMessageBox.information(self, "No Updates", "You are already using the latest version.")

    def edit_username_event(self, event):
        current_name = self.username_label.text().replace("User: ", "")
        dialog = EditUsernameDialog(current_name, self)
        if dialog.exec():
            if dialog.new_username:
                self.username_label.setText(f"User: {dialog.new_username}")

    def load_ui_state(self):
        """Loads the UI state from settings."""
        settings = load_settings()
        
        # Download Settings
        dl_settings = settings.get('download', {})
        
        ext_text = dl_settings.get('extension', "Best")
        idx = self.extension_combo.findText(ext_text)
        if idx >= 0: self.extension_combo.setCurrentIndex(idx)
        
        name_text = dl_settings.get('naming', "Original Name")
        idx = self.naming_combo.findText(name_text)
        if idx >= 0: self.naming_combo.setCurrentIndex(idx)
        
        self.subs_checkbox.setChecked(dl_settings.get('subtitles', False))
        
        self.video_download_path = dl_settings.get('video_path', "")
        if self.video_download_path:
            self.video_path_button.setText(f"Video: {self.video_download_path}")
            self.video_path_button.setToolTip(self.video_download_path)
            
        self.photo_download_path = dl_settings.get('photo_path', "")
        if self.photo_download_path:
            self.photo_path_button.setText(f"Photo: {self.photo_download_path}")
            self.photo_path_button.setToolTip(self.photo_download_path)
            
        # User Profile
        username = settings.get('user_profile', {}).get('username', "Guest")
        self.username_label.setText(f"User: {username}")

        # System Settings
        sys_settings = settings.get('system', {})
        self.shutdown_checkbox.setChecked(sys_settings.get('shutdown', False))
        
        # Threads (Only set if valid and saved)
        saved_threads = sys_settings.get('threads', 4)
        if saved_threads > 0:
             self.threads_spinbox.setValue(saved_threads)

    def get_ui_state(self):
        """Returns the current UI state as a dictionary for saving."""
        username = self.username_label.text().replace("User: ", "")
        return {
            'user_profile': {
                'username': username
            },
            'download': {
                'extension': self.extension_combo.currentText(),
                'naming': self.naming_combo.currentText(),
                'subtitles': self.subs_checkbox.isChecked(),
                'video_path': self.video_download_path if self.video_download_path else "",
                'photo_path': self.photo_download_path if self.photo_download_path else ""
            },
            'system': {
                'threads': self.threads_spinbox.value(),
                'shutdown': self.shutdown_checkbox.isChecked()
            }
        }

    @Slot()
    def select_video_path(self):
        """Opens a file dialog to select the download directory for videos."""
        path = QFileDialog.getExistingDirectory(self, "Select Video Download Path")
        if path:
            self.video_download_path = path
            self.video_path_button.setText(f"Video: {path}")
            self.video_path_button.setToolTip(path)
            self.status_message.emit(f"Video download path set to: {path}")

    @Slot()
    def select_photo_path(self):
        """Opens a file dialog to select the download directory for photos."""
        path = QFileDialog.getExistingDirectory(self, "Select Photo Download Path")
        if path:
            self.photo_download_path = path
            self.photo_path_button.setText(f"Photo: {path}")
            self.photo_path_button.setToolTip(path)
            self.status_message.emit(f"Photo download path set to: {path}")

    @Slot(str, str)
    def add_to_queue_display(self, item_id, url):
        """Adds an item to the left-hand 'URL Queue' table."""
        row_position = self.queue_table_widget.rowCount()
        self.queue_table_widget.insertRow(row_position)
        self.queue_table_widget.setItem(row_position, 0, QTableWidgetItem(str(row_position + 1))) # Add row number
        self.queue_table_widget.setItem(row_position, 1, QTableWidgetItem(url)) # URL in second column
        self.active_download_map[item_id] = row_position

    @Slot(str)
    def remove_from_queue_display(self, item_id):
        """Removes an item from the 'URL Queue' table once it's finished."""
        if item_id in self.active_download_map:
            row_to_remove = self.active_download_map.pop(item_id)
            self.queue_table_widget.removeRow(row_to_remove)
            # Note: This is a simple removal. A more robust solution would need to
            # re-index the self.active_download_map if rows are not always removed from the end.
            # For now, this is sufficient as we are not re-ordering.

    def validate_url_input(self):
        """Validates the current text in the URL input and provides visual feedback."""
        url = self.url_input.text().strip()
        if not url:
            self.url_input.setStyleSheet("""
                QLineEdit {
                    background-color: #1C1C21;
                    border: 2px solid #27272A;
                    border-radius: 15px;
                    padding: 0 8px;
                    color: #F4F4F5;
                    font-size: 10pt;
                }
                QLineEdit:focus { border-color: #3B82F6; background-color: #202025; }
            """)
            return True

        handler = self.platform_handler_factory.get_handler(url)
        if handler:
            # Valid URL
            self.url_input.setStyleSheet("""
                QLineEdit {
                    background-color: #1C1C21;
                    border: 2px solid #10B981; /* Green border for valid */
                    border-radius: 15px;
                    padding: 0 8px;
                    color: #F4F4F5;
                    font-size: 10pt;
                }
                QLineEdit:focus { border-color: #34D399; background-color: #202025; }
            """)
            return True
        else:
            # Invalid URL
            self.url_input.setStyleSheet("""
                QLineEdit {
                    background-color: #1C1C21;
                    border: 2px solid #EF4444; /* Red border for invalid */
                    border-radius: 15px;
                    padding: 0 8px;
                    color: #F4F4F5;
                    font-size: 10pt;
                }
                QLineEdit:focus { border-color: #F87171; background-color: #202025; }
            """)
            return False

    @Slot()
    def add_url_to_download_queue(self):
        # LICENSE GATE
        if not self.check_license_gate():
            return

        url = self.url_input.text().strip()
        if not url:
            self.status_message.emit("Please enter a URL to add to queue.")
            return

        if not self.validate_url_input():
            self.status_message.emit("Unsupported platform. Please enter a valid URL (YouTube, FB, TikTok, etc.)")
            return

        # Check for duplicates
        for row in range(self.queue_table_widget.rowCount()):
            item = self.queue_table_widget.item(row, 1) # Check URL column
            if item and item.text() == url:
                self.status_message.emit(f"URL already in queue: {url}")
                self.url_input.clear()
                return

        row_position = self.queue_table_widget.rowCount()
        self.queue_table_widget.insertRow(row_position)
        self.queue_table_widget.setItem(row_position, 0, QTableWidgetItem(str(row_position + 1))) # Add row number
        self.queue_table_widget.setItem(row_position, 1, QTableWidgetItem(url)) # URL in second column
        self.status_message.emit("Added to queue")
        self.url_input.clear() # Clear input after adding to queue

    def set_settings_tab(self, settings_tab):
        """Sets the reference to the settings tab."""
        self.settings_tab = settings_tab

    def open_license_dialog(self):
        dialog = LicenseDialog(self)
        if dialog.exec():
            self.update_license_ui()

    def update_license_ui(self):
        is_valid, msg, _ = self.license_manager.get_license_status()
        if is_valid:
            self.license_status_button.setText("Licensed")
            # Load and set the tick icon
            icon_path = resource_path("app/resources/images/icons/checklist.png")
            self.license_status_button.setIcon(QIcon(icon_path))
            # Set the icon size for better appearance
            self.license_status_button.setIconSize(QSize(16, 16)) # Assuming 16x16 is a good size for a 30px high button

            self.license_status_button.setStyleSheet("""
                QPushButton {
                    background-color: #1C1C21;
                    color: #10B981; /* Green */
                    border: 1px solid #27272A;
                    border-radius: 15px; /* Matches 50% of 30px height */
                    padding: 0 12px;
                    font-size: 9pt;
                    font-weight: 600;
                }
                QPushButton:hover { border-color: #10B981; }
            """)
        else:
            self.license_status_button.setText("Activate License")
            self.license_status_button.setIcon(QIcon()) # Clear icon when not licensed
            self.license_status_button.setStyleSheet("""
                QPushButton {
                    background-color: #1C1C21;
                    color: #EF4444; /* Red */
                    border: 1px solid #27272A;
                    border-radius: 15px; /* Matches 50% of 30px height */
                    padding: 0 12px;
                    font-size: 9pt;
                    font-weight: 600;
                }
                QPushButton:hover { border-color: #EF4444; }
            """)

    def check_license_gate(self):
        """Checks license before performing an action. Returns True if valid."""
        is_valid, msg, _ = self.license_manager.get_license_status()
        if is_valid:
            return True
        
        # License Invalid -> Prompt User
        reply = QMessageBox.question(
            self, 
            "License Required", 
            f"This feature requires a valid license.\nReason: {msg}\n\nDo you want to activate now?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.open_license_dialog()
            # Re-check after dialog closes
            is_valid_after, _, _ = self.license_manager.get_license_status()
            return is_valid_after
            
        return False

    def scrap_url(self):
        """
        Initiates the scraping process for the URL in the input field.
        """
        # LICENSE GATE
        if not self.check_license_gate():
            return

        url = self.url_input.text().strip()
        if not url:
            self.status_message.emit("Please enter a URL to scrap.")
            return
        
        if not self.validate_url_input():
            self.status_message.emit("Unsupported platform for scraping.")
            return
        
        self.process_scraping(url)

    def process_scraping(self, urls):
        """Helper method to handle the scraping logic for given URLs using background threads."""
        if isinstance(urls, str):
            urls = [urls]
            
        if not hasattr(self, 'active_scraping_workers'):
            self.active_scraping_workers = []

        self.handle_status_message(f"Scraping {len(urls)} URLs...")
        self.scrap_button.setEnabled(False)

        # Get base settings once
        base_settings = {}
        if self.settings_tab:
            base_settings = self.settings_tab.get_settings()
            print(f"[DEBUG] process_scraping retrieved base settings: {base_settings}")
        else:
            print("[ERROR] Settings tab not linked!")

        for url in urls:
            # Create a copy of settings for this URL to inject specific credentials
            settings = base_settings.copy()
            
            # --- Inject Platform Credentials for Scraper ---
            # Facebook
            if "facebook.com" in url or "fb.watch" in url:
                creds = self.credentials_manager.get_credential('facebook')
                if creds:
                    if creds.get('cookie_file'): settings['cookie_file'] = creds.get('cookie_file')
                    if creds.get('browser') and creds.get('browser') != "None": settings['cookies_from_browser'] = creds.get('browser')

            # YouTube
            elif "youtube.com" in url or "youtu.be" in url:
                creds = self.credentials_manager.get_credential('youtube')
                if creds:
                    if creds.get('cookie_file'): settings['cookie_file'] = creds.get('cookie_file')
                    if creds.get('browser') and creds.get('browser') != "None": settings['cookies_from_browser'] = creds.get('browser')

            # Pinterest
            elif "pinterest.com" in url:
                creds = self.credentials_manager.get_credential('pinterest')
                if creds:
                    if creds.get('cookie_file'): settings['cookie_file'] = creds.get('cookie_file')
                    if creds.get('browser') and creds.get('browser') != "None": settings['cookies_from_browser'] = creds.get('browser')

            # TikTok
            elif "tiktok.com" in url:
                creds = self.credentials_manager.get_credential('tiktok')
                if creds:
                    if creds.get('cookie_file'): settings['cookie_file'] = creds.get('cookie_file')
                    if creds.get('browser') and creds.get('browser') != "None": settings['cookies_from_browser'] = creds.get('browser')

            # Instagram
            elif "instagram.com" in url:
                creds = self.credentials_manager.get_credential('instagram')
                if creds:
                    if creds.get('cookie_file'): settings['cookie_file'] = creds.get('cookie_file')
                    if creds.get('browser') and creds.get('browser') != "None": settings['cookies_from_browser'] = creds.get('browser')
                        
            print(f"[DEBUG] Starting worker for {url} with settings: {settings}")

            # Create and start worker
            worker = ScrapingWorker(url, self.platform_handler_factory, settings, parent=self)
            worker.item_found.connect(self.on_scraping_item_found)
            # Use lambda with default argument to capture current worker reference
            worker.finished.connect(lambda w=worker: self.on_scraping_worker_finished(w))
            worker.error.connect(self.on_scraping_error)
            worker.status_update.connect(self.handle_status_message) # Connect new signal
            
            self.active_scraping_workers.append(worker)
            worker.start()

    @Slot(str, dict, bool, bool, object)
    def on_scraping_item_found(self, item_url, metadata, is_video, is_photo, handler):
        """Slot to handle an item found by the scraping worker."""
        try:
            print(f"[DEBUG] on_scraping_item_found RECEIVED for: {item_url} (Video: {is_video}, Photo: {is_photo})")
            
            # Get current settings again for fresh download options if needed, 
            # but mostly we use what was passed to worker or defaults.
            # Actually, we need to build 'download_settings' here to pass to downloader.
            
            settings = {}
            if self.settings_tab:
                 settings = self.settings_tab.get_settings()
            
            video_opts = settings.get('video', {})
            photo_opts = settings.get('photo', {})
    
            download_settings = {}
            if is_video:
                 download_settings['resolution'] = video_opts.get('resolution', "Best Available")
            if is_photo:
                 download_settings['quality'] = photo_opts.get('quality', "Best Available")
            
            print(f"[DEBUG] Calculated download_settings: {download_settings}")
            
            # Pass origin URL to settings for folder organization
            if 'origin_url' in metadata:
                download_settings['origin_url'] = metadata['origin_url']
            
            # --- Inject Platform Credentials for Download ---
            if "facebook.com" in item_url or "fb.watch" in item_url:
                creds = self.credentials_manager.get_credential('facebook')
                if creds:
                    if creds.get('cookie_file'): download_settings['cookie_file'] = creds.get('cookie_file')
                    if creds.get('browser') and creds.get('browser') != "None": download_settings['cookies_from_browser'] = creds.get('browser')

            elif "youtube.com" in item_url or "youtu.be" in item_url:
                creds = self.credentials_manager.get_credential('youtube')
                if creds:
                    if creds.get('cookie_file'): download_settings['cookie_file'] = creds.get('cookie_file')
                    if creds.get('browser') and creds.get('browser') != "None": download_settings['cookies_from_browser'] = creds.get('browser')

            elif "pinterest.com" in item_url:
                creds = self.credentials_manager.get_credential('pinterest')
                if creds:
                    if creds.get('cookie_file'): download_settings['cookie_file'] = creds.get('cookie_file')
                    if creds.get('browser') and creds.get('browser') != "None": download_settings['cookies_from_browser'] = creds.get('browser')

            elif "tiktok.com" in item_url:
                creds = self.credentials_manager.get_credential('tiktok')
                if creds:
                    if creds.get('cookie_file'): download_settings['cookie_file'] = creds.get('cookie_file')
                    if creds.get('browser') and creds.get('browser') != "None": download_settings['cookies_from_browser'] = creds.get('browser')

            elif "instagram.com" in item_url:
                creds = self.credentials_manager.get_credential('instagram')
                if creds:
                    if creds.get('cookie_file'): download_settings['cookie_file'] = creds.get('cookie_file')
                    if creds.get('browser') and creds.get('browser') != "None": download_settings['cookies_from_browser'] = creds.get('browser')

            # Add to Backend Queue
            item_id = self.downloader.add_to_queue(item_url, handler, download_settings)
            print(f"[DEBUG] Added to backend queue: {item_id}")
            
            # Add to UI Table
            row_position_activity = self.activity_table.rowCount()
            print(f"[DEBUG] Inserting row at {row_position_activity} for {item_url}")
            self.activity_table.insertRow(row_position_activity)
            self.activity_table.setItem(row_position_activity, 0, QTableWidgetItem(str(row_position_activity + 1)))
            self.activity_table.setItem(row_position_activity, 1, QTableWidgetItem(metadata.get('title', '')))
            
            url_widget = QTableWidgetItem(item_url)
            if 'origin_url' in metadata:
                url_widget.setData(Qt.UserRole, metadata['origin_url'])
            self.activity_table.setItem(row_position_activity, 2, url_widget)
            
            self.activity_table.setItem(row_position_activity, 3, QTableWidgetItem("Queued"))
            self.activity_table.setItem(row_position_activity, 4, QTableWidgetItem("Video" if is_video else "Photo"))
            self.activity_table.setItem(row_position_activity, 5, QTableWidgetItem(handler.__class__.__name__.replace('Handler','')))
            self.activity_table.setItem(row_position_activity, 6, QTableWidgetItem("--"))
            self.activity_table.setItem(row_position_activity, 7, QTableWidgetItem("--"))
            
            progress_bar = QProgressBar()
            progress_bar.setRange(0, 100)
            progress_bar.setValue(0)
            progress_bar.setTextVisible(True)
            progress_bar.setAlignment(Qt.AlignCenter)
            progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #27272A;
                    border-radius: 5px;
                    text-align: center;
                    color: #F4F4F5;
                    background-color: #1C1C21;
                }
                QProgressBar::chunk {
                    background-color: #3B82F6;
                    width: 10px;
                }
            """)
            self.activity_table.setCellWidget(row_position_activity, 8, progress_bar)
            
            self.activity_row_map[item_id] = row_position_activity
            print(f"[DEBUG] Added to UI table at row {row_position_activity}")

        except Exception as e:
            print(f"[ERROR] Failed to add item to UI: {e}")
            import traceback
            traceback.print_exc()

    def on_scraping_worker_finished(self, worker):
        """Internal handler for individual worker completion."""
        if hasattr(self, 'active_scraping_workers') and worker in self.active_scraping_workers:
            self.active_scraping_workers.remove(worker)
        
        if not getattr(self, 'active_scraping_workers', []):
            self.on_scraping_finished()

    @Slot()
    def on_scraping_finished(self):
        self.status_message.emit("All scraping tasks completed.")
        self.scrap_button.setEnabled(True)

    @Slot(str)
    def on_scraping_error(self, message):
        self.status_message.emit(message)

    def open_queue_context_menu(self, position):
        from PySide6.QtWidgets import QMenu
        menu = QMenu()
        scrap_action = menu.addAction("🔍 Scrap Now")
        scrap_action.triggered.connect(self.scrap_selected_queue_item)
        
        copy_action = menu.addAction("📋 Copy URL")
        copy_action.triggered.connect(self.copy_selected_queue_urls)

        menu.addSeparator()
        
        delete_action = menu.addAction("🗑️ Delete")
        delete_action.triggered.connect(self.delete_selected_queue_item)
        
        menu.exec(self.queue_table_widget.viewport().mapToGlobal(position))

    def open_activity_context_menu(self, position):
        from PySide6.QtWidgets import QMenu
        menu = QMenu()
        
        selected_items = self.activity_table.selectedItems()
        selected_rows = set(item.row() for item in selected_items)
        
        select_all_action = menu.addAction("✅ Select All")
        select_all_action.triggered.connect(self.select_all_activity_items)
        
        menu.addSeparator()

        # Add "Open Folder" only if exactly one item is selected
        if len(selected_rows) == 1:
            open_folder_action = menu.addAction("📁 Open Folder")
            open_folder_action.triggered.connect(self.open_selected_item_folder)
            menu.addSeparator()
        
        download_action = menu.addAction("⬇️ Download Selected")
        download_action.triggered.connect(self.download_selected_activity_items)
        
        copy_action = menu.addAction("📋 Copy URL")
        copy_action.triggered.connect(self.copy_selected_activity_urls)

        menu.addSeparator()
        
        delete_action = menu.addAction("❌ Remove Row")
        delete_action.triggered.connect(self.delete_selected_activity_item)
        
        menu.exec(self.activity_table.viewport().mapToGlobal(position))

    def select_all_activity_items(self):
        """Selects all rows in the activity table."""
        self.activity_table.selectAll()

    def download_selected_activity_items(self):
        """Promotes selected items to the top of the queue and starts downloading."""
        selected_rows = set()
        has_video_work = False
        has_photo_work = False

        for item in self.activity_table.selectedItems():
            row = item.row()
            selected_rows.add(row)
            
            # Check item type for validation
            type_item = self.activity_table.item(row, 4) # Column 4 is Type
            if type_item:
                item_type = type_item.text()
                if "Video" in item_type:
                    has_video_work = True
                elif "Photo" in item_type:
                    has_photo_work = True
            
        if not selected_rows:
            return

        # Validate Paths
        if has_video_work and not self.video_download_path:
            QMessageBox.warning(self, "Video Path Missing", "You have selected videos to download.\nPlease select a Video Download Path.")
            return
            
        if has_photo_work and not self.photo_download_path:
            QMessageBox.warning(self, "Photo Path Missing", "You have selected photos to download.\nPlease select a Photo Download Path.")
            return
            
        # Find item IDs for the selected rows
        item_ids = []
        for row in selected_rows:
            # Inefficient reverse lookup, but safe given existing structure
            for i_id, r_idx in self.activity_row_map.items():
                if r_idx == row:
                    item_ids.append(i_id)
                    break
        
        if item_ids:
            # Filter item_ids to only those in the downloader queue (pending/held)
            valid_ids = self.downloader.filter_existing_ids(item_ids)
            skipped_count = len(item_ids) - len(valid_ids)

            msg = f"Starting {len(valid_ids)} selected downloads..."
            if skipped_count > 0:
                msg += f" ({skipped_count} items skipped/completed)"
            # self.status_message.emit(msg) # Removed to avoid mode conflict
            
            # Update global progress bar for selected batch
            self.update_footer_mode("progress") # Switch to progress bar
            self.total_downloads = len(item_ids) # Total is what user selected
            self.completed_downloads = skipped_count # Treat missing ones as 'done'
            self.failed_downloads = 0 
            
            self.global_progress_bar.setRange(0, self.total_downloads)
            self.global_progress_bar.setValue(self.completed_downloads)
            self.global_progress_bar.setFormat("Completed: %v / %m")

            if not valid_ids:
                # If all selected items were already done, trigger summary immediately
                self.download_finished_callback("dummy", True) # Hacky trigger or manual check?
                # Better: Manual check
                if (self.completed_downloads + self.failed_downloads) == self.total_downloads:
                     CustomMessageBox("Download Summary", f"All selected items processed.\n\nSkipped/Completed: {skipped_count}", self).exec()
                return

            # Update settings for queue items before starting
            settings = {
                'video_path': self.video_download_path,
                'photo_path': self.photo_download_path,
                'extension': self.extension_combo.currentText().lower(),
                'naming_style': self.naming_combo.currentText(),
                'subtitles': self.subs_checkbox.isChecked(),
                'shutdown': self.shutdown_checkbox.isChecked()
            }
            self.downloader.update_queue_settings(settings)
            
            # Promote and Queue selected items
            self.downloader.promote_to_front(valid_ids)
            self.downloader.queue_items(valid_ids)
            
            # Reset counts if starting fresh or just update UI?
            # We'll just ensure timer is running
            if not self.timer.isActive():
                self.start_timer()
                
            self.downloader.process_queue()

    def open_selected_item_folder(self):
        """Opens the folder containing the selected item in the OS file explorer."""
        import os
        import subprocess
        import sys

        selected_items = self.activity_table.selectedItems()
        if not selected_items:
            return
        
        row = selected_items[0].row()
        url_item = self.activity_table.item(row, 2) # URL is in column 2
        type_item = self.activity_table.item(row, 4) # Type is in column 4
        
        if not url_item or not type_item:
            return
            
        url = url_item.text()
        is_video = "Video" in type_item.text()
        origin_url = url_item.data(Qt.UserRole) # We will store origin_url in UserRole
        
        # Determine base path
        base_path = self.video_download_path if is_video else self.photo_download_path
        if not base_path:
            # Fallback to the other path if one is missing, then to current dir
            base_path = self.photo_download_path if is_video else self.video_download_path
        if not base_path:
            base_path = "."

        # Reconstruct path using handler logic
        handler = self.platform_handler_factory.get_handler(url)
        if handler:
            settings = {
                'video_path': self.video_download_path,
                'photo_path': self.photo_download_path,
                'origin_url': origin_url
            }
            target_folder = handler.get_download_path(settings, is_video=is_video, item_url=url)
        else:
            target_folder = base_path

        # Create path if it doesn't exist (optional, but avoids explorer errors)
        if not os.path.exists(target_folder):
            try:
                os.makedirs(target_folder, exist_ok=True)
            except Exception:
                target_folder = base_path # Fallback to base

        # Open in explorer
        try:
            if sys.platform == 'win32':
                os.startfile(os.path.abspath(target_folder))
            elif sys.platform == 'darwin': # macOS
                subprocess.run(['open', target_folder])
            else: # Linux
                subprocess.run(['xdg-open', target_folder])
        except Exception as e:
            self.status_message.emit(f"Could not open folder: {e}")

    def delete_selected_activity_item(self):
        """Removes the selected row from the activity table."""
        selected_rows = set()
        for item in self.activity_table.selectedItems():
            selected_rows.add(item.row())
        
        for row in sorted(selected_rows, reverse=True):
            self.activity_table.removeRow(row)
            
        # Re-number
        for row in range(self.activity_table.rowCount()):
            self.activity_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))

    def scrap_selected_queue_item(self):
        selected_items = self.queue_table_widget.selectedItems()
        if not selected_items:
            return
        
        # Collect unique URLs from all selected rows
        urls = set()
        for item in selected_items:
            row = item.row()
            url_item = self.queue_table_widget.item(row, 1) # URL is in column 1
            if url_item:
                urls.add(url_item.text())
        
        if urls:
            self.process_scraping(list(urls))

    def copy_selected_queue_urls(self):
        """Copies the URLs of selected rows in the queue table to the clipboard."""
        from PySide6.QtWidgets import QApplication
        selected_items = self.queue_table_widget.selectedItems()
        if not selected_items:
            return
        
        urls = []
        selected_rows = set()
        for item in selected_items:
            selected_rows.add(item.row())
            
        for row in sorted(list(selected_rows)):
            url_item = self.queue_table_widget.item(row, 1) # URL is in column 1
            if url_item:
                urls.append(url_item.text())
        
        if urls:
            clipboard = QApplication.clipboard()
            clipboard.setText("\n".join(urls))
            self.status_message.emit(f"Copied {len(urls)} URL(s) to clipboard.")

    def copy_selected_activity_urls(self):
        """Copies the URLs of selected rows in the activity table to the clipboard."""
        from PySide6.QtWidgets import QApplication
        selected_items = self.activity_table.selectedItems()
        if not selected_items:
            return
        
        urls = []
        selected_rows = set()
        for item in selected_items:
            selected_rows.add(item.row())
            
        for row in sorted(list(selected_rows)):
            url_item = self.activity_table.item(row, 2) # URL is in column 2
            if url_item:
                urls.append(url_item.text())
        
        if urls:
            clipboard = QApplication.clipboard()
            clipboard.setText("\n".join(urls))
            self.status_message.emit(f"Copied {len(urls)} URL(s) to clipboard.")

    def delete_selected_queue_item(self):
        """Removes the selected row from the queue table."""
        selected_rows = set()
        for item in self.queue_table_widget.selectedItems():
            selected_rows.add(item.row())
        
        # Remove rows in reverse order to maintain indices
        for row in sorted(selected_rows, reverse=True):
            self.queue_table_widget.removeRow(row)
        
        # Optional: Re-number the '#' column after deletion
        for row in range(self.queue_table_widget.rowCount()):
            self.queue_table_widget.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        
    def update_thread_count(self, count):
        """Updates the maximum thread count in the downloader."""
        self.downloader.set_max_threads(count)

    def start_timer(self):
        self.seconds_elapsed = 0
        self.update_timer_display()
        self.timer.start(1000)

    def stop_timer(self):
        self.timer.stop()

    def reset_timer(self):
        self.stop_timer()
        self.seconds_elapsed = 0
        self.update_timer_display()

    def update_timer_display(self):
        if self.timer.isActive():
            self.seconds_elapsed += 1
        
        hours = self.seconds_elapsed // 3600
        minutes = (self.seconds_elapsed % 3600) // 60
        seconds = self.seconds_elapsed % 60
        
        self.timer_label.setText(f"{hours:02}:{minutes:02}:{seconds:02}")

    @Slot(float, float, float)
    def update_network_stats(self, down_mbps, up_mbps, ping_ms):
        """Updates the network speed and ping display."""
        # Format: Ping: 25ms  ↓ 12.5 Mbps  ↑ 5.2 Mbps
        self.speed_label.setText(f"Ping: {int(ping_ms)}ms   ↓ {down_mbps:.2f} Mbps   ↑ {up_mbps:.2f} Mbps")

    @Slot()
    def start_download_from_queue(self):
        # Check if paths are selected
        if not self.video_download_path and not self.photo_download_path:
            QMessageBox.warning(self, "Download Paths Missing", "Please select a Video or Photo download path first.")
            return

        # Update settings in downloader
        settings = {
            'video_path': self.video_download_path,
            'photo_path': self.photo_download_path,
            'extension': self.extension_combo.currentText().lower(),
            'naming_style': self.naming_combo.currentText(),
            'subtitles': self.subs_checkbox.isChecked(),
            'shutdown': self.shutdown_checkbox.isChecked()
        }
        self.downloader.update_queue_settings(settings)

        # We need to process the items that are in the queue_table_widget
        # For now, just trigger the downloader's process_queue
        if self.downloader.queue_empty():
            self.status_message.emit("Download queue is empty.")
            return
        
        self.status_message.emit("Starting downloads from queue...")
        self.start_timer() # Start the timer
        self.downloader.process_queue()

    @Slot()
    def cancel_all_downloads(self):
        """Stops the timer and clears queue (placeholder for real cancel logic)."""
        # In a real app, we'd iterate and cancel workers. 
        # For now, just stop logic in UI
        self.stop_timer()
        self.status_message.emit("Downloads cancelled (Timer stopped).")

    @Slot(str, str)
    def update_download_status(self, item_id, message):
        """Updates the status of an item in the activity table."""
        if item_id in self.activity_row_map:
            row = self.activity_row_map[item_id]
            self.activity_table.setItem(row, 3, QTableWidgetItem(message))
            
        # Optional: Also log to console/global status if needed, or just keep it clean
        # self.status_message.emit(f"ID {item_id[:8]}... status: {message}")
        # print(f"Update status for {item_id[:8]}...: {message}")

    @Slot(str)
    def handle_status_message(self, message):
        """Updates the global status label and ensures it is visible."""
        self.global_status_label.setText(message)
        self.update_footer_mode("status")

    def update_footer_mode(self, mode):
        """Switches footer display between 'status' (Label) and 'progress' (Bar)."""
        if mode == "progress":
            self.global_status_label.setVisible(False)
            self.global_progress_bar.setVisible(True)
        else:
            self.global_progress_bar.setVisible(False)
            self.global_status_label.setVisible(True)

    @Slot(str)
    def update_status_message(self, message):
        """Legacy Slot to update the global status label."""
        self.handle_status_message(message)

    def _update_footer_progress(self, item_id, percentage):
        """Updates or adds a progress bar in the footer for the given item."""
        if item_id not in self.active_progress_bars:
            # Create new bar container
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(10)
            
            label = QLabel(f"Download {item_id[:6]}...")
            label.setStyleSheet("color: #A1A1AA; font-size: 9pt;")
            
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(percentage)
            bar.setFixedHeight(10)
            bar.setTextVisible(False)
            bar.setStyleSheet("""
                QProgressBar {
                    background-color: #27272A;
                    border-radius: 5px;
                }
                QProgressBar::chunk {
                    background-color: #3B82F6;
                    border-radius: 5px;
                }
            """)
            
            layout.addWidget(label)
            layout.addWidget(bar)
            
            self.active_downloads_layout.addWidget(container)
            self.active_progress_bars[item_id] = {
                'widget': container,
                'bar': bar,
                'label': label
            }
        else:
            # Update existing bar
            self.active_progress_bars[item_id]['bar'].setValue(percentage)

    @Slot(str, int)
    def update_download_progress(self, item_id, percentage):
        """Updates the progress of an item in the activity table."""
        # Footer progress update removed (replaced by global batch bar)
        # self._update_footer_progress(item_id, percentage)
        
        # Update Table Progress
        if item_id in self.activity_row_map:
            row = self.activity_row_map[item_id]
            pb = self.activity_table.cellWidget(row, 8)
            if pb:
                pb.setValue(percentage)
                
        # print(f"Update progress for {item_id[:8]}...: {percentage}%")

    @Slot(str, bool)
    def download_finished_callback(self, item_id, success):
        """Handles the completion or failure of a download."""
        # Remove from footer (logic removed in init, but good to cleanup if we kept dict)
        if item_id in self.active_progress_bars:
             # Just cleanup dict
             del self.active_progress_bars[item_id]
        
        # Update Table
        if item_id in self.activity_row_map:
            row = self.activity_row_map[item_id]
            status = "Completed" if success else "Failed"
            self.activity_table.setItem(row, 3, QTableWidgetItem(status))
            
            pb = self.activity_table.cellWidget(row, 8)
            if pb:
                pb.setValue(100 if success else 0)
        
        if success:
            self.completed_downloads += 1
            print(f"Download finished for {item_id[:8]}... Success: {success}")
        else:
             self.failed_downloads += 1
             print(f"Failed: {item_id[:8]}...")

        # Update global progress bar (it counts processed items, whether success or fail)
        self.global_progress_bar.setValue(self.completed_downloads + self.failed_downloads)

        # Check if all downloads are finished
        if (self.completed_downloads + self.failed_downloads) == self.total_downloads and self.total_downloads > 0:
            self.stop_timer()
            
            self.update_footer_mode("status")
            self.global_status_label.setText(f"Total: {self.total_downloads} | Completed: {self.completed_downloads} | Failed: {self.failed_downloads}")

    @Slot()
    def start_download_from_queue(self):
        # Determine if we have work to do for Videos or Photos
        has_video_work = False
        has_photo_work = False
        
        # 1. Check Settings (Proactive check)
        if self.settings_tab:
            settings = self.settings_tab.get_settings()
            if settings.get('video', {}).get('enabled', False):
                has_video_work = True
            if settings.get('photo', {}).get('enabled', False):
                has_photo_work = True
        
        # 2. Check Queue Content (Reactive check - if manual items or scraped items exist)
        # Iterate rows in activity_table
        for row in range(self.activity_table.rowCount()):
            type_item = self.activity_table.item(row, 4) # Column 4 is 'Type'
            status_item = self.activity_table.item(row, 3) # Column 3 is 'Status'
            
            if type_item and status_item and status_item.text() != "Completed":
                item_type = type_item.text()
                if "Video" in item_type:
                    has_video_work = True
                elif "Photo" in item_type:
                    has_photo_work = True
        
        # Validate Paths
        if has_video_work and not self.video_download_path:
            QMessageBox.warning(self, "Video Path Missing", "You have Video Download enabled or videos in queue.\nPlease select a Video Download Path.")
            return
            
        if has_photo_work and not self.photo_download_path:
            QMessageBox.warning(self, "Photo Path Missing", "You have Photo Download enabled or photos in queue.\nPlease select a Photo Download Path.")
            return

        # Update settings in downloader
        settings = {
            'video_path': self.video_download_path,
            'photo_path': self.photo_download_path,
            'extension': self.extension_combo.currentText().lower(),
            'naming_style': self.naming_combo.currentText(),
            'subtitles': self.subs_checkbox.isChecked(),
            'shutdown': self.shutdown_checkbox.isChecked()
        }
        self.downloader.update_queue_settings(settings)

        # We need to process the items that are in the queue_table_widget
        # For now, just trigger the downloader's process_queue
        if self.downloader.queue_empty():
            self.status_message.emit("Download queue is empty.")
            return
        
        # Reset counts
        self.total_downloads = len(self.downloader.queue) 
        self.completed_downloads = 0
        self.failed_downloads = 0 # Reset failed count
        
        self.global_progress_bar.setRange(0, self.total_downloads)
        self.global_progress_bar.setValue(0)
        self.global_progress_bar.setFormat("Completed: %v / %m")
        # self.status_message.emit(f"Completed: 0 / {self.total_downloads}")
        
        self.status_message.emit("Starting downloads from queue...")
        
        # Queue all items (change status from held to queued)
        self.downloader.queue_all()
        
        self.start_timer() # Start the timer
        self.downloader.process_queue()