from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QStyle
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QMouseEvent

class CustomDialogBase(QDialog):
    """
    A base class for dialogs with a custom dark-themed, draggable title bar.
    Subclasses should add their content to self.content_layout.
    """
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setStyleSheet("""
            QDialog {
                background-color: #18181B; 
                border: 1px solid #3F3F46;
                border-radius: 8px;
            }
            QLabel { color: #F4F4F5; }
        """)
        
        self.old_pos = None

        # --- Main Layout ---
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # --- Custom Title Bar ---
        self.title_bar = QFrame()
        self.title_bar.setFixedHeight(32)
        self.title_bar.setStyleSheet("""
            QFrame {
                background-color: #27272A;
                border-bottom: 1px solid #3F3F46;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
        """)
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(10, 0, 5, 0)
        
        # Title Label
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 10pt; border: none; background: transparent;")
        title_layout.addWidget(self.title_label)
        
        title_layout.addStretch()
        
        # Close Button
        self.close_btn = QPushButton()
        self.close_btn.setIcon(self.style().standardIcon(QStyle.SP_TitleBarCloseButton))
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.clicked.connect(self.reject)
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
        title_layout.addWidget(self.close_btn)
        
        self.main_layout.addWidget(self.title_bar)

        # --- Content Area ---
        content_widget = QFrame()
        content_widget.setStyleSheet("background-color: #18181B; border: none; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;")
        self.content_layout = QVBoxLayout(content_widget)
        self.content_layout.setSpacing(10)
        self.content_layout.setContentsMargins(15, 15, 15, 15)
        
        self.main_layout.addWidget(content_widget)

    # --- Window Dragging Logic ---
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            # Check if clicked on title bar area (approximate height)
            if event.pos().y() <= 32:
                self.old_pos = event.globalPos()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.old_pos:
            delta = event.globalPos() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.old_pos = None
