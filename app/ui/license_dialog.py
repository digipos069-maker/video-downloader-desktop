from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPushButton, QHBoxLayout, 
    QMessageBox, QApplication
)
from PySide6.QtCore import Qt
from app.config.license_manager import LicenseManager
from app.ui.widgets.custom_dialog import CustomDialogBase

class LicenseDialog(CustomDialogBase):
    def __init__(self, parent=None):
        super().__init__(title="Activate License", parent=parent)
        self.setFixedSize(400, 300)
        
        self.license_manager = LicenseManager()
        
        # --- Content ---
        # Add content to self.content_layout provided by base class

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
                padding: 4px 8px; 
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
                padding: 6px 12px;
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
                padding: 4px 8px; 
                border-radius: 4px;
                color: #F4F4F5;
            }
            QLineEdit:focus { border-color: #3B82F6; }
        """)
        self.content_layout.addWidget(self.key_input)

        # Activate Button
        self.activate_btn = QPushButton("Activate License")
        self.activate_btn.setCursor(Qt.PointingHandCursor)
        self.activate_btn.setFixedHeight(35)
        self.activate_btn.setStyleSheet("""
            QPushButton {
                background-color: #10B981; 
                color: white; 
                font-weight: bold; 
                border-radius: 6px;
                font-size: 10pt;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        self.activate_btn.clicked.connect(self.activate)
        self.content_layout.addWidget(self.activate_btn)
        
        self.content_layout.addStretch()
        
        self.check_current_status()

    def check_current_status(self):
        is_valid, msg, _ = self.license_manager.get_license_status()
        if is_valid:
            self.status_label.setText(f"Active: {msg}")
            self.status_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #10B981;") # Green
            self.activate_btn.setText("Update License")
            self.key_input.setText("License is valid.")
            # Make close button red to indicate "Active/Done" state visually if desired
            self.close_btn.setStyleSheet("""
                QPushButton {
                    background-color: #EF4444;
                    border: none;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #DC2626;
                }
            """)
        else:
            self.status_label.setText("License Required")
            self.status_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #EF4444;") # Red
            # Reset close button style for inactive state
            self.close_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #EF4444;
                }
            """)

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