"""
The main UI for the downloader tab.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QGroupBox, QTabWidget, QAbstractItemView,
    QHeaderView, QSizePolicy, QMessageBox, QSpacerItem, QTableWidgetItem,
    QFileDialog, QComboBox, QFormLayout, QCheckBox, QSpinBox, QFrame, QProgressBar
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QThread

from app.platform_handler import PlatformHandlerFactory
from app.downloader import Downloader
from app.network import NetworkMonitor
from app.config.settings_manager import load_settings

class ScrapingWorker(QThread):
    item_found = Signal(str, dict, bool, bool, object) # item_url, metadata, is_video, is_photo, handler
    finished = Signal()
    error = Signal(str)

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
                 fetch_limit = 200 # Increased limit for 'all'
            elif target_count > 0:
                 fetch_limit = target_count + 5 # Fetch a few more than target just in case of filters
            
            metadata_list = handler.get_playlist_metadata(self.url, max_entries=fetch_limit)
            
            if not metadata_list:
                self.error.emit(f"No downloadable items found for {self.url}.")
                return

            print(f"[DEBUG] Total items scraped: {len(metadata_list)}")

            video_count = 0
            photo_count = 0
            filtered_count = 0

            for metadata in metadata_list:
                try:
                    item_url = metadata['url']
                    print(f"[DEBUG] Processing URL: {item_url}")
                    
                    is_video = item_url.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm'))
                    is_photo = item_url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))
                    
                    if not is_video and not is_photo:
                        if any(x in item_url for x in ['youtube', 'youtu.be', 'tiktok', 'facebook']):
                            is_video = True
                        elif 'instagram' in item_url:
                            is_photo = True
                    
                    # Apply Filters
                    if is_video and not video_enabled:
                        filtered_count += 1
                        continue
                    if is_photo and not photo_enabled:
                        filtered_count += 1
                        continue
                        
                    if is_video:
                        if limit_video and video_count >= video_opts.get('count', 5):
                            filtered_count += 1
                            continue
                        video_count += 1
                            
                    if is_photo:
                        if limit_photo and photo_count >= photo_opts.get('count', 5):
                            filtered_count += 1
                            continue
                        photo_count += 1

                    self.item_found.emit(item_url, metadata, is_video, is_photo, handler)
                except Exception as loop_error:
                    print(f"[ERROR] Loop failed for item {metadata}: {loop_error}")
                    continue
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
        self.active_progress_bars = {} # item_id -> QProgressBar widget

        # --- Network Monitor Setup ---
        self.network_monitor = NetworkMonitor(self)
        self.network_monitor.stats_signal.connect(self.update_network_stats)
        self.network_monitor.start()

        # --- UI Layout ---
        main_layout = QVBoxLayout(self) # Changed to QVBoxLayout
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # --- Top Bar (Two Rows) ---
        top_bar_layout = QVBoxLayout()
        top_bar_layout.setSpacing(10)

        # Row 1: Logo, Network Speed, User
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(15)

        self.logo_label = QLabel("Logo") 
        self.logo_label.setFixedSize(64, 64)
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.logo_label.setStyleSheet("background-color: #383e48; border-radius: 32px; font-weight: bold;")
        
        # Speed Info Box
        speed_box = QFrame()
        speed_box.setFixedHeight(36)
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
        speed_layout.setContentsMargins(12, 0, 12, 0)
        self.speed_label = QLabel("↓ 0.00 Mbps / ↑ 0.00 Mbps")
        self.speed_label.setObjectName("speed_label")
        speed_layout.addWidget(self.speed_label)

        # User Info Box
        user_box = QFrame()
        user_box.setFixedHeight(36)
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
        user_layout.setContentsMargins(12, 0, 12, 0)
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
        self.timer_label.setFixedSize(100, 36)
        self.timer_label.setStyleSheet("""
            QLabel {
                background-color: #1C1C21;
                border: 1px solid #27272A;
                border-radius: 8px;
                color: #10B981; /* Green for timer */
                font-weight: bold;
                font-size: 11pt;
                font-family: Consolas, "Courier New", monospace;
            }
        """)
        row1_layout.addWidget(self.timer_label)
        
        row1_layout.addStretch()
        
        # Top Right Buttons (Update & License)
        self.check_update_button = QPushButton("Check Update")
        self.check_update_button.setCursor(Qt.PointingHandCursor)
        self.check_update_button.setFixedHeight(30)
        self.check_update_button.setStyleSheet("""
            QPushButton {
                background-color: #1C1C21;
                color: #A1A1AA;
                border: 1px solid #27272A;
                border-radius: 15px;
                padding: 0 12px;
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
                padding: 0 12px;
                font-size: 9pt;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #27272A;
                border-color: #F59E0B;
            }
        """)
        
        row1_layout.addWidget(self.check_update_button)
        row1_layout.addWidget(self.license_status_button)
        
        top_bar_layout.addLayout(row1_layout)

        # Row 2: Input, Buttons, Supported Icons
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(10) 
        
        input_block_layout = QHBoxLayout()
        input_block_layout.setSpacing(5)
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste video URL here...")
        self.url_input.setFixedHeight(35)
        self.url_input.setStyleSheet("""
            QLineEdit {
                background-color: #1C1C21;
                border: 2px solid #27272A;
                border-radius: 17px; /* approx 50% of 35px */
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
        self.add_to_queue_button.setFixedHeight(35)
        self.add_to_queue_button.clicked.connect(self.add_url_to_download_queue)
        self.add_to_queue_button.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: white;
                border-radius: 17px;
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
        self.scrap_button.setFixedHeight(35)
        self.scrap_button.clicked.connect(self.scrap_url)
        self.scrap_button.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: white;
                border-radius: 17px;
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
        
        input_block_layout.addWidget(self.url_input)
        input_block_layout.addWidget(self.add_to_queue_button)
        input_block_layout.addWidget(self.scrap_button)
        
        row2_layout.addLayout(input_block_layout)
        row2_layout.addStretch()
        
        # Supported Platform Icons
        platform_icons_layout = QHBoxLayout()
        platform_icons_layout.setSpacing(5) # Spacing between icons
        platform_icons_layout.setAlignment(Qt.AlignRight | Qt.AlignVCenter) # Align icons to the right and vertically center

        # Helper to create a circular icon label with an image
        def create_circular_icon_with_image(image_path, tooltip):
            icon_label = QLabel()
            icon_label.setFixedSize(30, 30) # Small circular icon
            icon_label.setAlignment(Qt.AlignCenter)
            
            # Use a stylesheet for circular shape and background, image is set via QPixmap
            icon_label.setStyleSheet(
                "border-radius: 15px; " # Half of width/height for circular shape
                "background-color: #383838; " # A neutral background for the circle
                "border: 1px solid #555555;" # Optional: add a subtle border
            )

            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                # Scale pixmap to fit inside the 30x30 label, preserving aspect ratio
                scaled_pixmap = pixmap.scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                icon_label.setPixmap(scaled_pixmap)
            else:
                # Fallback if image not found, display '?'
                icon_label.setText("?") 
                icon_label.setStyleSheet(icon_label.styleSheet() + "color: white; font-weight: bold;")
                
            icon_label.setToolTip(tooltip)
            return icon_label

        # Base path for icons - assuming images are in app/resources/images/
        icon_base_path = "app/resources/images/" 

        # Add icons for supported platforms (YouTube, TikTok, Facebook)
        platform_icons_layout.addWidget(create_circular_icon_with_image(icon_base_path + "youtube.png", "YouTube"))
        platform_icons_layout.addWidget(create_circular_icon_with_image(icon_base_path + "tiktok.png", "TikTok"))
        platform_icons_layout.addWidget(create_circular_icon_with_image(icon_base_path + "facebook.png", "Facebook"))
        
        row2_layout.addLayout(platform_icons_layout)
        
        top_bar_layout.addLayout(row2_layout)

        # --- Content Area (Two Columns) ---
        content_layout = QHBoxLayout()
        content_layout.setSpacing(15)

        # --- Left Sidebar ---
        left_sidebar_widget = QWidget()
        left_sidebar_layout = QVBoxLayout(left_sidebar_widget)
        left_sidebar_layout.setContentsMargins(0, 0, 0, 0)
        left_sidebar_layout.setSpacing(10)
        left_sidebar_widget.setFixedWidth(280)

        # --- Right Side (Main Content) ---
        right_content_layout = QVBoxLayout()
        right_content_layout.setSpacing(10)
        
        # --- Left Sidebar Widgets ---
        queue_group = QGroupBox("Downloading Queue")
        queue_layout = QVBoxLayout()
        self.queue_table_widget = QTableWidget()
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
        paths_layout.setSpacing(10)
        
        path_btn_style = """
            QPushButton {
                background-color: #1C1C21;
                color: #A1A1AA;
                border: 1px solid #27272A;
                border-radius: 8px;
                padding: 5px;
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

        left_sidebar_layout.addWidget(queue_group)
        left_sidebar_layout.addWidget(paths_group)
        left_sidebar_layout.addStretch()
        
        # --- Right Content Widgets ---
        activity_group = QGroupBox("Download Activity")
        activity_layout = QVBoxLayout()
        activity_layout.setContentsMargins(0, 10, 0, 0) 

        # Activity Table
        self.activity_table = QTableWidget()
        self.activity_table.setColumnCount(9)
        self.activity_table.setHorizontalHeaderLabels(["#", "Title", "URL", "Status", "Type", "Platform", "ETA", "Size", "Progress"])
        self.activity_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents) # For '#' column
        for i in range(1, 9):
            self.activity_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)
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
        settings_layout.setSpacing(20)
        
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
        self.naming_combo.addItems(["Original Name", "Numbered (01. Name)"])
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
        system_layout.setSpacing(12)
        
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
        
        # Active Downloads Area (Dynamic)
        self.active_downloads_container = QWidget()
        self.active_downloads_layout = QVBoxLayout(self.active_downloads_container)
        self.active_downloads_layout.setContentsMargins(0, 0, 0, 10)
        self.active_downloads_layout.setSpacing(5)
        footer_main_layout.addWidget(self.active_downloads_container)

        # Footer Controls
        footer_layout = QHBoxLayout()
        self.global_status_label = QLabel("Completed: 0 / 0")
        self.global_status_label.setObjectName("global_status_label")
        self.global_status_label.setStyleSheet("color: #3B82F6; font-weight: bold; font-size: 10pt;")
        self.status_message.connect(self.update_status_message) # Custom handler for status text if needed
        
        action_btn_style = """
             QPushButton {
                border-radius: 17px; /* 50% of 35px height */
                padding: 0 12px;
                font-weight: bold;
                font-size: 11pt;
            }
        """
        
        self.download_button = QPushButton("Download All")
        self.download_button.setCursor(Qt.PointingHandCursor)
        self.download_button.setFixedHeight(35)
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
        self.cancel_button.setFixedHeight(35)
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
        
        footer_layout.addWidget(self.global_status_label)
        footer_layout.addStretch()
        footer_layout.addWidget(self.download_button)
        footer_layout.addWidget(self.cancel_button)
        
        footer_main_layout.addLayout(footer_layout)

        # --- Assemble Right Layout ---
        right_content_layout.addWidget(activity_group)
        right_content_layout.addLayout(bottom_controls_layout)
        right_content_layout.addLayout(footer_main_layout)
        
        # --- Assemble Content Layout ---
        content_layout.addWidget(left_sidebar_widget)
        content_layout.addLayout(right_content_layout)

        # --- Assemble Main Layout ---
        main_layout.addLayout(top_bar_layout)
        main_layout.addLayout(content_layout)

        # Load initial UI state
        self.load_ui_state()

    def edit_username_event(self, event):
        from PySide6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self, 'Edit Username', 'Enter new username:')
        if ok and text:
            self.username_label.setText(f"User: {text}")

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

        # System Settings
        sys_settings = settings.get('system', {})
        self.shutdown_checkbox.setChecked(sys_settings.get('shutdown', False))
        
        # Threads (Only set if valid and saved)
        saved_threads = sys_settings.get('threads', 4)
        if saved_threads > 0:
             self.threads_spinbox.setValue(saved_threads)

    def get_ui_state(self):
        """Returns the current UI state as a dictionary for saving."""
        return {
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
        """Adds an item to the left-hand 'Downloading Queue' table."""
        row_position = self.queue_table_widget.rowCount()
        self.queue_table_widget.insertRow(row_position)
        self.queue_table_widget.setItem(row_position, 0, QTableWidgetItem(str(row_position + 1))) # Add row number
        self.queue_table_widget.setItem(row_position, 1, QTableWidgetItem(url)) # URL in second column
        self.active_download_map[item_id] = row_position

    @Slot(str)
    def remove_from_queue_display(self, item_id):
        """Removes an item from the 'Downloading Queue' table once it's finished."""
        if item_id in self.active_download_map:
            row_to_remove = self.active_download_map.pop(item_id)
            self.queue_table_widget.removeRow(row_to_remove)
            # Note: This is a simple removal. A more robust solution would need to
            # re-index the self.active_download_map if rows are not always removed from the end.
            # For now, this is sufficient as we are not re-ordering.

    @Slot()
    def add_url_to_download_queue(self):
        url = self.url_input.text().strip()
        if not url:
            self.status_message.emit("Please enter a URL to add to queue.")
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
        self.status_message.emit(f"URL added to queue: {url}")
        self.url_input.clear() # Clear input after adding to queue

    def set_settings_tab(self, settings_tab):
        """Sets the reference to the settings tab."""
        self.settings_tab = settings_tab

    @Slot()
    def scrap_url(self):
        url = self.url_input.text().strip()
        if not url:
            self.status_message.emit("Please enter a URL to scrap.")
            return
        self.process_scraping(url)

    def process_scraping(self, url):
        """Helper method to handle the scraping logic for a given URL using a background thread."""
        self.status_message.emit(f"Scraping URL: {url}...")
        
        # Get settings
        settings = {}
        if self.settings_tab:
            settings = self.settings_tab.get_settings()
            print(f"[DEBUG] Scraping with settings: {settings}")
        else:
            print("[ERROR] Settings tab not linked!")

        # Create and start worker
        self.scraping_worker = ScrapingWorker(url, self.platform_handler_factory, settings, parent=self)
        self.scraping_worker.item_found.connect(self.on_scraping_item_found)
        self.scraping_worker.finished.connect(self.on_scraping_finished)
        self.scraping_worker.error.connect(self.on_scraping_error)
        self.scraping_worker.start()
        
        self.scrap_button.setEnabled(False) # Disable button while scraping

    @Slot(str, dict, bool, bool, object)
    def on_scraping_item_found(self, item_url, metadata, is_video, is_photo, handler):
        """Slot to handle an item found by the scraping worker."""
        try:
            print(f"[DEBUG] on_scraping_item_found called for: {item_url}")
            
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
    
            # Add to Backend Queue
            item_id = self.downloader.add_to_queue(item_url, handler, download_settings)
            print(f"[DEBUG] Added to backend queue: {item_id}")
            
            # Add to UI Table
            row_position_activity = self.activity_table.rowCount()
            self.activity_table.insertRow(row_position_activity)
            self.activity_table.setItem(row_position_activity, 0, QTableWidgetItem(str(row_position_activity + 1)))
            self.activity_table.setItem(row_position_activity, 1, QTableWidgetItem(metadata.get('title', 'N/A')))
            self.activity_table.setItem(row_position_activity, 2, QTableWidgetItem(item_url))
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

    @Slot()
    def on_scraping_finished(self):
        self.status_message.emit("Scraping completed.")
        self.scrap_button.setEnabled(True)
        # Clean up worker


    @Slot(str)
    def on_scraping_error(self, message):
        self.status_message.emit(message)
        self.scrap_button.setEnabled(True)

    def open_queue_context_menu(self, position):
        from PySide6.QtWidgets import QMenu
        menu = QMenu()
        scrap_action = menu.addAction("Scrap")
        scrap_action.triggered.connect(self.scrap_selected_queue_item)
        
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(self.delete_selected_queue_item)
        
        menu.exec(self.queue_table_widget.viewport().mapToGlobal(position))

    def open_activity_context_menu(self, position):
        from PySide6.QtWidgets import QMenu
        menu = QMenu()
        
        download_action = menu.addAction("Download Selected")
        download_action.triggered.connect(self.download_selected_activity_items)
        
        menu.addSeparator()
        
        add_queue_action = menu.addAction("Add to Queue")
        add_queue_action.triggered.connect(self.add_selected_activity_to_queue)
        
        delete_action = menu.addAction("Remove Row")
        delete_action.triggered.connect(self.delete_selected_activity_item)
        
        menu.exec(self.activity_table.viewport().mapToGlobal(position))

    def download_selected_activity_items(self):
        """Promotes selected items to the top of the queue and starts downloading."""
        selected_rows = set()
        for item in self.activity_table.selectedItems():
            selected_rows.add(item.row())
            
        if not selected_rows:
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
            self.status_message.emit(f"Starting {len(item_ids)} selected downloads...")
            
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
            self.downloader.promote_to_front(item_ids)
            self.downloader.queue_items(item_ids)
            
            # Reset counts if starting fresh or just update UI?
            # We'll just ensure timer is running
            if not self.timer.isActive():
                self.start_timer()
                
            self.downloader.process_queue()

    def add_selected_activity_to_queue(self):
        selected_rows = set()
        for item in self.activity_table.selectedItems():
            selected_rows.add(item.row())
            
        if not selected_rows:
            return

        # Gather current settings
        settings = {
            'video_path': self.video_download_path,
            'photo_path': self.photo_download_path,
            'extension': self.extension_combo.currentText().lower(),
            'naming_style': self.naming_combo.currentText(),
            'subtitles': self.subs_checkbox.isChecked(),
            'shutdown': self.shutdown_checkbox.isChecked()
        }
        
        count = 0
        for row in sorted(selected_rows):
            url_item = self.activity_table.item(row, 2) # URL is column 2
            if url_item:
                url = url_item.text()
                handler = self.platform_handler_factory.get_handler(url)
                if handler:
                    item_id = self.downloader.add_to_queue(url, handler, settings.copy())
                    self.activity_table.setItem(row, 3, QTableWidgetItem("Queued")) # Update status
                    self.activity_row_map[item_id] = row
                    
                    # Reset Progress Bar
                    pb = self.activity_table.cellWidget(row, 8)
                    if pb:
                        pb.setValue(0)
                    
                    count += 1
        
        if count > 0:
            self.status_message.emit(f"Re-queued {count} items. Click 'Download All' to start.")

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
        
        # In a row selection, we get all items in the row.
        # We want the URL, which is in column 1.
        # We can find the row index of the first selected item.
        row = selected_items[0].row()
        url_item = self.queue_table_widget.item(row, 1)
        if url_item:
            self.process_scraping(url_item.text())

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
    def update_status_message(self, message):
        """Slot to update the global status label."""
        self.global_status_label.setText(message)

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
        """Updates the progress of an item in the activity table and footer."""
        # Update footer progress
        self._update_footer_progress(item_id, percentage)
        
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
        # Remove from footer
        if item_id in self.active_progress_bars:
            widget = self.active_progress_bars[item_id]['widget']
            self.active_downloads_layout.removeWidget(widget)
            widget.deleteLater()
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
            self.status_message.emit(f"Completed: {self.completed_downloads} / {self.total_downloads}")
            print(f"Download finished for {item_id[:8]}... Success: {success}")
        else:
             self.status_message.emit(f"Failed: {item_id[:8]}...")

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
        self.downloader.update_queue_settings(settings);

        # We need to process the items that are in the queue_table_widget
        # For now, just trigger the downloader's process_queue
        if self.downloader.queue_empty():
            self.status_message.emit("Download queue is empty.")
            return
        
        # Reset counts
        self.total_downloads = len(self.downloader.queue) 
        self.completed_downloads = 0
        self.status_message.emit(f"Completed: 0 / {self.total_downloads}")
        
        self.status_message.emit("Starting downloads from queue...")
        
        # Queue all items (change status from held to queued)
        self.downloader.queue_all()
        
        self.start_timer() # Start the timer
        self.downloader.process_queue()