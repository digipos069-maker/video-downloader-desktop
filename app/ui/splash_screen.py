
from PySide6.QtWidgets import QSplashScreen, QProgressBar, QVBoxLayout, QLabel, QWidget, QFrame
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QPixmap, QColor, QFont, QPainter, QIcon
from app.helpers import resource_path
import os

class ModernSplashScreen(QSplashScreen):
    def __init__(self):
        # Create a base pixmap for the splash screen
        # We will paint on it initially, but then overlay widgets
        pixmap = QPixmap(450, 320)
        pixmap.fill(QColor("#101014")) # Dark background
        super().__init__(pixmap, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        
        self.setFixedSize(450, 320)
        
        # Setup Main Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 40, 20, 20)
        layout.setSpacing(15)
        layout.setAlignment(Qt.AlignCenter)

        # --- Logo ---
        logo_label = QLabel()
        logo_path = resource_path(os.path.join("app", "resources", "images", "logo.png"))
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path)
            pix = pix.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(pix)
        else:
            logo_label.setText("SDM")
            logo_label.setStyleSheet("font-size: 40px; color: #3B82F6; font-weight: bold;")
        
        logo_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo_label)

        # --- App Name ---
        title_label = QLabel("SDM")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            color: #3B82F6;
            font-family: 'Segoe UI', sans-serif;
            font-size: 32px;
            font-weight: bold;
            letter-spacing: 2px;
        """)
        layout.addWidget(title_label)
        
        # --- Subtitle ---
        subtitle_label = QLabel("Social Download Manager")
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("""
            color: #71717A;
            font-family: 'Segoe UI', sans-serif;
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 10px;
        """)
        layout.addWidget(subtitle_label)

        layout.addStretch()

        # --- Loading Container ---
        loading_container = QVBoxLayout()
        loading_container.setSpacing(5)

        # Loading Text
        self.loading_label = QLabel("Initializing...")
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setStyleSheet("color: #A1A1AA; font-size: 11px;")
        loading_container.addWidget(self.loading_label)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #27272A;
                border-radius: 3px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #3B82F6, stop:1 #60A5FA);
                border-radius: 3px;
            }
        """)
        loading_container.addWidget(self.progress_bar)
        
        layout.addLayout(loading_container)

    def update_progress(self, value, message=None):
        self.progress_bar.setValue(value)
        if message:
            self.loading_label.setText(message)
        # Force UI update
        self.repaint()
