from PySide6.QtWidgets import (
    QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout
)
from PySide6.QtCore import Qt
from app.ui.widgets.custom_dialog import CustomDialogBase

class EditUsernameDialog(CustomDialogBase):
    def __init__(self, current_username, parent=None):
        super().__init__(title="Edit Username", parent=parent)
        self.setFixedSize(350, 180)
        self.new_username = None

        # Input Field
        self.username_input = QLineEdit(current_username)
        self.username_input.setPlaceholderText("Enter new username...")
        self.username_input.setStyleSheet("""
            QLineEdit {
                background-color: #27272A;
                border: 1px solid #3F3F46;
                padding: 8px;
                border-radius: 4px;
                color: #F4F4F5;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border-color: #3B82F6;
            }
        """)
        self.content_layout.addWidget(self.username_input)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #A1A1AA;
                border: 1px solid #3F3F46;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #27272A;
                color: white;
            }
        """)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self.save_username)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: white;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
        """)
        btn_layout.addWidget(save_btn)

        self.content_layout.addLayout(btn_layout)

    def save_username(self):
        text = self.username_input.text().strip()
        if text:
            self.new_username = text
            self.accept()
        else:
            self.username_input.setFocus()
