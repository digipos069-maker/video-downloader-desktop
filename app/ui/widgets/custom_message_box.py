from PySide6.QtWidgets import (
    QVBoxLayout, QLabel, QPushButton, QHBoxLayout
)
from PySide6.QtCore import Qt
from app.ui.widgets.custom_dialog import CustomDialogBase

class CustomMessageBox(CustomDialogBase):
    """
    A custom replacement for QMessageBox using the app's design system.
    """
    def __init__(self, title, message, parent=None):
        super().__init__(title=title, parent=parent)
        self.setFixedSize(400, 160)

        # Message Label
        self.message_label = QLabel(message)
        self.message_label.setWordWrap(True)
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setStyleSheet("""
            QLabel {
                color: #F4F4F5;
                font-size: 10pt;
            }
        """)
        self.content_layout.addWidget(self.message_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.ok_btn = QPushButton("OK")
        self.ok_btn.setCursor(Qt.PointingHandCursor)
        self.ok_btn.setFixedWidth(100)
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.setStyleSheet("""
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
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addStretch()

        self.content_layout.addLayout(btn_layout)
