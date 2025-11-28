
"""
The UI for the Settings tab.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QTabWidget, QHBoxLayout, 
    QCheckBox, QSpinBox, QComboBox, QLabel, QFormLayout
)

class SettingsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # --- Styles ---
        input_style = """
            QComboBox, QSpinBox {
                background-color: #1C1C21;
                border: 2px solid #27272A;
                border-radius: 8px;
                padding: 4px 8px;
                color: #F4F4F5;
                font-size: 10pt;
                min-width: 80px;
            }
            QComboBox:hover, QSpinBox:hover {
                border-color: #3B82F6;
                background-color: #202025;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QCheckBox {
                color: #F4F4F5;
                font-size: 10pt;
                background-color: transparent;
                spacing: 8px;
            }
            QCheckBox::indicator {
                border: 2px solid #3F3F46;
                border-radius: 4px;
                width: 18px;
                height: 18px;
                background: transparent;
            }
            QCheckBox::indicator:checked {
                background-color: #3B82F6;
                border-color: #3B82F6;
            }
        """
        
        label_style = "color: #A1A1AA; font-weight: 600; background-color: transparent;"

        # --- Global Settings ---
        global_settings_layout = QHBoxLayout()
        global_settings_layout.setSpacing(20)

        # 1. Video Settings Box
        video_group = QGroupBox("Video Settings")
        video_layout = QVBoxLayout()
        video_layout.setSpacing(15)

        self.enable_video_chk = QCheckBox("Enable Video Download")
        self.enable_video_chk.setStyleSheet(input_style)
        
        # Top Videos Row
        top_video_layout = QHBoxLayout()
        self.top_video_chk = QCheckBox("Top Videos")
        self.top_video_chk.setStyleSheet(input_style)
        
        self.top_video_count = QSpinBox()
        self.top_video_count.setRange(1, 100)
        self.top_video_count.setValue(5)
        self.top_video_count.setStyleSheet(input_style)
        
        top_video_layout.addWidget(self.top_video_chk)
        top_video_layout.addWidget(self.top_video_count)
        top_video_layout.addStretch()

        self.all_video_chk = QCheckBox("All Videos")
        self.all_video_chk.setStyleSheet(input_style)
        
        # Resolution Row
        res_layout = QHBoxLayout()
        res_label = QLabel("Resolution:")
        res_label.setStyleSheet(label_style)
        
        self.video_res_combo = QComboBox()
        self.video_res_combo.addItems(["Best Available", "4K", "1080p", "720p", "480p", "360p"])
        self.video_res_combo.setStyleSheet(input_style)
        
        res_layout.addWidget(res_label)
        res_layout.addWidget(self.video_res_combo)
        res_layout.addStretch()

        video_layout.addWidget(self.enable_video_chk)
        video_layout.addLayout(top_video_layout)
        video_layout.addWidget(self.all_video_chk)
        video_layout.addLayout(res_layout)
        video_layout.addStretch()
        video_group.setLayout(video_layout)

        # 2. Photo Settings Box
        photo_group = QGroupBox("Photo Settings")
        photo_layout = QVBoxLayout()
        photo_layout.setSpacing(15)

        self.enable_photo_chk = QCheckBox("Enable Photo Download")
        self.enable_photo_chk.setStyleSheet(input_style)
        
        # Top Photos Row
        top_photo_layout = QHBoxLayout()
        self.top_photo_chk = QCheckBox("Top Photos")
        self.top_photo_chk.setStyleSheet(input_style)
        
        self.top_photo_count = QSpinBox()
        self.top_photo_count.setRange(1, 100)
        self.top_photo_count.setValue(5)
        self.top_photo_count.setStyleSheet(input_style)
        
        top_photo_layout.addWidget(self.top_photo_chk)
        top_photo_layout.addWidget(self.top_photo_count)
        top_photo_layout.addStretch()

        self.all_photo_chk = QCheckBox("All Photos")
        self.all_photo_chk.setStyleSheet(input_style)
        
        # Resolution (Quality) Row
        photo_res_layout = QHBoxLayout()
        photo_res_label = QLabel("Quality:")
        photo_res_label.setStyleSheet(label_style)
        
        self.photo_res_combo = QComboBox()
        self.photo_res_combo.addItems(["Best Available", "High", "Medium", "Low"])
        self.photo_res_combo.setStyleSheet(input_style)
        
        photo_res_layout.addWidget(photo_res_label)
        photo_res_layout.addWidget(self.photo_res_combo)
        photo_res_layout.addStretch()

        photo_layout.addWidget(self.enable_photo_chk)
        photo_layout.addLayout(top_photo_layout)
        photo_layout.addWidget(self.all_photo_chk)
        photo_layout.addLayout(photo_res_layout)
        photo_layout.addStretch()
        photo_group.setLayout(photo_layout)

        # Add boxes to global layout
        global_settings_layout.addWidget(video_group)
        global_settings_layout.addWidget(photo_group)

        # Global Header
        global_header = QLabel("Global Settings")
        global_header.setStyleSheet("color: #3B82F6; font-size: 12pt; font-weight: bold; margin-bottom: 2px;")
        layout.addWidget(global_header)

        layout.addLayout(global_settings_layout)

        # Platform Credentials Header
        cred_header = QLabel("Platform Credentials")
        cred_header.setStyleSheet("color: #3B82F6; font-size: 12pt; font-weight: bold; margin-bottom: 2px; margin-top: 15px;")
        layout.addWidget(cred_header)

        credentials_group = QGroupBox()
        credentials_group.setStyleSheet("QGroupBox { margin-top: 0px; }")
        cred_layout = QVBoxLayout()
        
        credentials_tabs = QTabWidget()
        credentials_tabs.addTab(QWidget(), "YouTube")
        credentials_tabs.addTab(QWidget(), "Instagram")
        credentials_tabs.addTab(QWidget(), "Pinterest")
        
        cred_layout.addWidget(credentials_tabs)
        credentials_group.setLayout(cred_layout)

        layout.addWidget(credentials_group)
        layout.addStretch() # Pushes the group to the top

if __name__ == '__main__':
    import sys, os
    from PySide6.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)
    
    # Applying the stylesheet for standalone testing
    style_file = os.path.join(os.path.dirname(__file__), "..", "resources", "styles.qss")
    if os.path.exists(style_file):
        with open(style_file, "r") as f:
            app.setStyleSheet(f.read())

    window = QMainWindow()
    settings_tab = SettingsTab()
    window.setCentralWidget(settings_tab)
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec())
