
"""
The UI for the Settings tab.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QTabWidget
)

class SettingsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Platform Credentials
        credentials_group = QGroupBox("Platform Credentials")
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
