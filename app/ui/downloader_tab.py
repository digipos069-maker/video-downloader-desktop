"""
The main UI for the downloader tab.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QGroupBox, QTabWidget, QAbstractItemView,
    QHeaderView, QSizePolicy, QMessageBox, QSpacerItem, QTableWidgetItem,
    QFileDialog, QComboBox, QFormLayout, QCheckBox
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, Signal, Slot

from app.platform_handler import PlatformHandlerFactory
from app.downloader import Downloader

class DownloaderTab(QWidget):
    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        
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
        
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        self.speed_label = QLabel("↓ 0.00 Mbps / ↑ 0.00 Mbps")
        self.speed_label.setObjectName("speed_label")
        self.username_label = QLabel("User: Guest")
        self.username_label.setObjectName("username_label")
        self.username_label.setCursor(Qt.PointingHandCursor)
        self.username_label.mousePressEvent = self.edit_username_event
        info_layout.addWidget(self.speed_label)
        info_layout.addWidget(self.username_label)
        
        row1_layout.addWidget(self.logo_label)
        row1_layout.addLayout(info_layout)
        row1_layout.addStretch()
        
        top_bar_layout.addLayout(row1_layout)

        # Row 2: Input, Buttons, Supported Icons
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(15) # Spacing between input block and icons
        
        input_block_layout = QHBoxLayout()
        input_block_layout.setSpacing(5) # Added spacing between input and buttons
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste URL here")
        self.url_input.setStyleSheet("border-radius: 15px; padding: 5px;") 
        
        self.add_to_queue_button = QPushButton("➕ Add to Queue")
        self.add_to_queue_button.setObjectName("add_to_queue_button")
        self.add_to_queue_button.clicked.connect(self.add_url_to_download_queue)
        self.add_to_queue_button.setStyleSheet("border-radius: 50%; padding: 5px;")
        
        self.scrap_button = QPushButton("⚡ Scrap")
        self.scrap_button.setObjectName("scrap_button")
        self.scrap_button.clicked.connect(self.scrap_url)
        self.scrap_button.setStyleSheet("border-radius: 50%; padding: 5px;")
        
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
        self.video_path_button = QPushButton("📁 Video Path...")
        self.video_path_button.clicked.connect(self.select_video_path)
        self.photo_path_button = QPushButton("📁 Photo Path...")
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
        self.activity_table.setHorizontalHeaderLabels(["#", "Title", "URL", "Status", "Progress", "Retries", "ETA", "Size", "Actions"])
        self.activity_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents) # For '#' column
        for i in range(1, 9):
            self.activity_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)
        self.activity_table.verticalHeader().setVisible(False)
        self.activity_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.activity_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        
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
            QComboBox {
                background-color: #2c313a;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 5px 10px;
                color: #eff0f1;
                font-size: 10pt;
                min-width: 100px;
            }
            QComboBox:hover {
                border: 1px solid #7E57C2;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 25px;
                border-left-width: 0px;
            }
            QComboBox::down-arrow {
                image: none; 
                border-left: 2px solid #eff0f1;
                border-bottom: 2px solid #eff0f1;
                width: 8px; 
                height: 8px;
                transform: rotate(-45deg);
                margin-top: -3px;
                margin-left: 2px;
            }
            QComboBox QAbstractItemView {
                background-color: #2c313a;
                border: 1px solid #555;
                selection-background-color: #7E57C2;
                selection-color: #eff0f1;
                outline: none;
            }
            QCheckBox {
                color: #eff0f1;
                font-size: 10pt;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #555;
                border-radius: 3px;
                background-color: #2c313a;
            }
            QCheckBox::indicator:checked {
                background-color: #7E57C2;
                border: 1px solid #7E57C2;
                image: url(none); /* Placeholder for checkmark if needed, color change is usually enough */
            }
        """

        # Extension Section (User's "File Type")
        ext_layout = QVBoxLayout()
        ext_layout.setSpacing(5)
        ext_label = QLabel("Extension")
        ext_label.setStyleSheet("color: #b1b1b1; font-weight: bold; font-size: 9pt; text-transform: uppercase;")
        self.extension_combo = QComboBox()
        self.extension_combo.addItems(["Best", "mp4", "mp3", "mkv", "wav", "jpg", "png"])
        self.extension_combo.setCursor(Qt.PointingHandCursor)
        self.extension_combo.setStyleSheet(input_style)
        ext_layout.addWidget(ext_label)
        ext_layout.addWidget(self.extension_combo)
        
        # Naming Style Section (User's "Video Format")
        naming_layout = QVBoxLayout()
        naming_layout.setSpacing(5)
        naming_label = QLabel("Naming Style")
        naming_label.setStyleSheet("color: #b1b1b1; font-weight: bold; font-size: 9pt; text-transform: uppercase;")
        self.naming_combo = QComboBox()
        self.naming_combo.addItems(["Original Name", "Numbered (01. Name)"])
        self.naming_combo.setCursor(Qt.PointingHandCursor)
        self.naming_combo.setStyleSheet(input_style)
        naming_layout.addWidget(naming_label)
        naming_layout.addWidget(self.naming_combo)
        
        # Extra Options Section
        options_layout = QVBoxLayout()
        options_layout.setSpacing(5)
        options_label = QLabel("Extras")
        options_label.setStyleSheet("color: #b1b1b1; font-weight: bold; font-size: 9pt; text-transform: uppercase;")
        self.subs_checkbox = QCheckBox("Download Subtitles")
        self.subs_checkbox.setCursor(Qt.PointingHandCursor)
        self.subs_checkbox.setStyleSheet(input_style)
        options_layout.addWidget(options_label)
        options_layout.addWidget(self.subs_checkbox)

        settings_layout.addLayout(ext_layout)
        settings_layout.addLayout(naming_layout)
        settings_layout.addLayout(options_layout)
        settings_layout.addStretch() 
        
        settings_group.setLayout(settings_layout)
        bottom_controls_layout.addWidget(settings_group)
        bottom_controls_layout.addStretch()

        # Footer for Status and Action Buttons
        footer_layout = QHBoxLayout()
        self.global_status_label = QLabel("Ready")
        self.global_status_label.setObjectName("global_status_label")
        self.status_message.connect(self.global_status_label.setText)
        
        self.download_button = QPushButton("⬇️ Download All")
        self.download_button.setObjectName("download_button")
        self.download_button.clicked.connect(self.start_download_from_queue)
        self.cancel_button = QPushButton("❌ Cancel All")
        
        footer_layout.addWidget(self.global_status_label)
        footer_layout.addStretch()
        footer_layout.addWidget(self.download_button)
        footer_layout.addWidget(self.cancel_button)

        # --- Assemble Right Layout ---
        right_content_layout.addWidget(activity_group)
        right_content_layout.addLayout(bottom_controls_layout)
        right_content_layout.addLayout(footer_layout)
        
        # --- Assemble Content Layout ---
        content_layout.addWidget(left_sidebar_widget)
        content_layout.addLayout(right_content_layout)

        # --- Assemble Main Layout ---
        main_layout.addLayout(top_bar_layout)
        main_layout.addLayout(content_layout)

    def edit_username_event(self, event):
        from PySide6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self, 'Edit Username', 'Enter new username:')
        if ok and text:
            self.username_label.setText(f"User: {text}")

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

    @Slot()
    def scrap_url(self):
        url = self.url_input.text().strip()
        if not url:
            self.status_message.emit("Please enter a URL to scrap.")
            return
        self.process_scraping(url)

    def process_scraping(self, url):
        """Helper method to handle the scraping logic for a given URL."""
        self.status_message.emit(f"Scraping URL: {url}...")
        handler = self.platform_handler_factory.get_handler(url)

        if handler:
            try:
                # Use the playlist method for all scraping
                metadata_list = handler.get_playlist_metadata(url)
                if metadata_list:
                    for metadata in metadata_list:
                        # Add to backend downloader queue
                        self.downloader.add_to_queue(metadata['url'], handler, {})
                        
                        # Add item to the main activity table on the right
                        row_position_activity = self.activity_table.rowCount()
                        self.activity_table.insertRow(row_position_activity)
                        self.activity_table.setItem(row_position_activity, 0, QTableWidgetItem(str(row_position_activity + 1))) # Row number
                        self.activity_table.setItem(row_position_activity, 1, QTableWidgetItem(metadata.get('title', 'N/A'))) # Title
                        self.activity_table.setItem(row_position_activity, 2, QTableWidgetItem(metadata['url'])) # URL
                        self.activity_table.setItem(row_position_activity, 3, QTableWidgetItem("Queued")) # Status
                        
                    self.status_message.emit(f"Found and queued {len(metadata_list)} items.")
                else:
                    self.status_message.emit(f"No downloadable items found for {url}.")
            except Exception as e:
                self.status_message.emit(f"Error scraping {url}: {e}")
                print(f"ERROR scraping {url}: {e}") # Also print for debugging
        else:
            self.status_message.emit(f"No handler found for URL: {url}")

    def open_queue_context_menu(self, position):
        from PySide6.QtWidgets import QMenu
        menu = QMenu()
        scrap_action = menu.addAction("Scrap")
        scrap_action.triggered.connect(self.scrap_selected_queue_item)
        
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(self.delete_selected_queue_item)
        
        menu.exec(self.queue_table_widget.viewport().mapToGlobal(position))

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
            'subtitles': self.subs_checkbox.isChecked()
        }
        self.downloader.update_queue_settings(settings)

        # We need to process the items that are in the queue_table_widget
        # For now, just trigger the downloader's process_queue
        if self.downloader.queue_empty():
            self.status_message.emit("Download queue is empty.")
            return
        self.status_message.emit("Starting downloads from queue...")
        self.downloader.process_queue()

    @Slot(str, str)
    def update_download_status(self, item_id, message):
        """Updates the status of an item in the activity table."""
        # Find the item in the activity table by item_id (need a mapping for this later)
        # For now, just update the global status message
        self.status_message.emit(f"ID {item_id[:8]}... status: {message}")
        print(f"Update status for {item_id[:8]}...: {message}")

    @Slot(str, int)
    def update_download_progress(self, item_id, percentage):
        """Updates the progress of an item in the activity table."""
        # Find the item in the activity table by item_id and update its progress bar
        print(f"Update progress for {item_id[:8]}...: {percentage}%")

    @Slot(str, bool)
    def download_finished_callback(self, item_id, success):
        """Handles the completion or failure of a download."""
        # Find the item in the activity table by item_id and update its final status
        if success:
            self.status_message.emit(f"ID {item_id[:8]}... completed.")
        else:
            self.status_message.emit(f"ID {item_id[:8]}... failed.")
        print(f"Download finished for {item_id[:8]}... Success: {success}")