from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, 
    QMessageBox, QApplication, QFrame
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QMouseEvent
from app.config.license_manager import LicenseManager

class LicenseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setFixedSize(400, 340)
        # Main container style with border to define window edges
        self.setStyleSheet("""
            QDialog {
                background-color: #18181B; 
                border: 1px solid #3F3F46;
                border-radius: 8px;
            }
            QLabel { color: #F4F4F5; }
        """)
        
        self.license_manager = LicenseManager()
        
        # --- Window Dragging Variables ---
        self.old_pos = None

        # --- Main Layout ---
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # --- Custom Title Bar ---
        self.title_bar = QFrame()
        self.title_bar.setFixedHeight(40)
        self.title_bar.setStyleSheet("""
            QFrame {
                background-color: #27272A;
                border-bottom: 1px solid #3F3F46;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
        """)
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(15, 0, 5, 0)
        
        # Title Label
        title_label = QLabel("Activate License")
        title_label.setStyleSheet("font-weight: bold; font-size: 10pt; border: none; background: transparent;")
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        # Close Button
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.clicked.connect(self.reject)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #A1A1AA;
                border: none;
                font-size: 12pt;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #EF4444;
                color: white;
            }
        """)
        title_layout.addWidget(self.close_btn)
        
        self.main_layout.addWidget(self.title_bar)

        # --- Content Area ---
        content_widget = QFrame()
        content_widget.setStyleSheet("background-color: #18181B; border: none; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;")
        self.content_layout = QVBoxLayout(content_widget)
        self.content_layout.setSpacing(15)
        self.content_layout.setContentsMargins(20, 20, 20, 20)

        # Status Header
        self.status_label = QLabel("License Required")
        self.status_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #EF4444;") # Red
        self.status_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(self.status_label)

        # HWID Section
        hwid_label = QLabel("Your Hardware ID (Send this to Admin):")
        hwid_label.setStyleSheet("color: #A1A1AA; font-size: 9pt;")
        self.content_layout.addWidget(hwid_label)

        hwid_box = QHBoxLayout()
        self.hwid_display = QLineEdit(self.license_manager.hwid)
        self.hwid_display.setReadOnly(True)
        self.hwid_display.setStyleSheet("""
            QLineEdit {
                background-color: #27272A; 
                border: 1px solid #3F3F46; 
                padding: 8px; 
                border-radius: 4px;
                color: #F4F4F5;
            }
        """)
        
        copy_btn = QPushButton("Copy")
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6; 
                color: white; 
                border-radius: 4px; 
                padding: 8px 15px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #2563EB; }
        """)
        copy_btn.clicked.connect(self.copy_hwid)
        
        hwid_box.addWidget(self.hwid_display)
        hwid_box.addWidget(copy_btn)
        self.content_layout.addLayout(hwid_box)

        # Input Section
        key_label = QLabel("Enter License Key:")
        key_label.setStyleSheet("color: #A1A1AA; font-size: 9pt; margin-top: 5px;")
        self.content_layout.addWidget(key_label)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Paste your key here...")
        self.key_input.setStyleSheet("""
            QLineEdit {
                background-color: #27272A; 
                border: 1px solid #3F3F46; 
                padding: 8px; 
                border-radius: 4px;
                color: #F4F4F5;
            }
            QLineEdit:focus { border-color: #3B82F6; }
        """)
        self.content_layout.addWidget(self.key_input)

        # Activate Button
        self.activate_btn = QPushButton("Activate License")
        self.activate_btn.setCursor(Qt.PointingHandCursor)
        self.activate_btn.setFixedHeight(40)
        self.activate_btn.setStyleSheet("""
            QPushButton {
                background-color: #10B981; 
                color: white; 
                font-weight: bold; 
                border-radius: 6px;
                font-size: 11pt;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        self.activate_btn.clicked.connect(self.activate)
        self.content_layout.addWidget(self.activate_btn)
        
        self.content_layout.addStretch()
        self.main_layout.addWidget(content_widget)
        
        self.check_current_status()

    # --- Window Dragging Logic ---
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            # Check if clicked on title bar area (approximate height)
            if event.pos().y() <= 40:
                self.old_pos = event.globalPos()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.old_pos:
            delta = event.globalPos() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.old_pos = None

    def check_current_status(self):
        is_valid, msg, _ = self.license_manager.get_license_status()
        if is_valid:
            self.status_label.setText(f"Active: {msg}")
            self.status_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #10B981;") # Green
            self.activate_btn.setText("Update License")
            self.key_input.setText("License is valid.")
        else:
            self.status_label.setText("License Required")
            self.status_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #EF4444;") # Red

    def copy_hwid(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.license_manager.hwid)
        original_text = self.activate_btn.text()
        self.activate_btn.setText("HWID Copied!")
        # Note: In a real app we might want a timer to reset this, 
        # but for simplicity we leave it or let it reset on next interaction logic if needed.
        # A simple repaint refresh or just leaving it is fine for this scope.

    def activate(self):
        key = self.key_input.text().strip()
        if not key or key == "License is valid.":
            if self.activate_btn.text() != "HWID Copied!": # Don't error if just clicked copy
                 QMessageBox.warning(self, "Error", "Please enter a key.")
            return

        is_valid, msg = self.license_manager.verify_key(key)
        if is_valid:
            if self.license_manager.save_license(key):
                QMessageBox.information(self, "Success", f"License Activated!\n{msg}")
                self.accept() # Close dialog
            else:
                QMessageBox.critical(self, "Error", "Could not save license file.")
        else:
            QMessageBox.critical(self, "Activation Failed", f"Invalid Key: {msg}")