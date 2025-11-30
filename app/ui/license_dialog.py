from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QMessageBox, QApplication
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QClipboard
from app.config.license_manager import LicenseManager

class LicenseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Activate License")
        self.setFixedSize(400, 300)
        self.setStyleSheet("background-color: #18181B; color: #F4F4F5;")
        
        self.license_manager = LicenseManager()
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(15)
        self.layout.setContentsMargins(20, 20, 20, 20)

        # Status Header
        self.status_label = QLabel("License Required")
        self.status_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #EF4444;") # Red
        self.status_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.status_label)

        # HWID Section
        hwid_label = QLabel("Your Hardware ID (Send this to Admin):")
        hwid_label.setStyleSheet("color: #A1A1AA; font-size: 9pt;")
        self.layout.addWidget(hwid_label)

        hwid_box = QHBoxLayout()
        self.hwid_display = QLineEdit(self.license_manager.hwid)
        self.hwid_display.setReadOnly(True)
        self.hwid_display.setStyleSheet("background-color: #27272A; border: 1px solid #3F3F46; padding: 8px; border-radius: 4px;")
        
        copy_btn = QPushButton("Copy")
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setStyleSheet("background-color: #3B82F6; color: white; border-radius: 4px; padding: 8px;")
        copy_btn.clicked.connect(self.copy_hwid)
        
        hwid_box.addWidget(self.hwid_display)
        hwid_box.addWidget(copy_btn)
        self.layout.addLayout(hwid_box)

        # Input Section
        key_label = QLabel("Enter License Key:")
        key_label.setStyleSheet("color: #A1A1AA; font-size: 9pt; margin-top: 10px;")
        self.layout.addWidget(key_label)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Paste your key here...")
        self.key_input.setStyleSheet("background-color: #27272A; border: 1px solid #3F3F46; padding: 8px; border-radius: 4px;")
        self.layout.addWidget(self.key_input)

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
        self.layout.addWidget(self.activate_btn)
        
        self.layout.addStretch()
        self.check_current_status()

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
        self.activate_btn.setText("HWID Copied!")
        # Reset text after delay (simulated by just leaving it or using a timer, keeping it simple)

    def activate(self):
        key = self.key_input.text().strip()
        if not key:
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
