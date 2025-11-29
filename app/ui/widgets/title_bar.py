from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QApplication
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPainter, QColor

class TitleBar(QWidget):
    def __init__(self, parent=None, title="Application"):
        super().__init__(parent)
        self.setFixedHeight(35)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("TitleBar")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(10)

        # Icon (Optional placeholder)
        # self.icon_label = QLabel()
        # self.icon_label.setPixmap(...) 
        # layout.addWidget(self.icon_label)

        # Title
        self.title_label = QLabel(title)
        self.title_label.setObjectName("TitleBarTitle")
        layout.addWidget(self.title_label)

        layout.addStretch()

        # Window Controls
        self.btn_minimize = QPushButton("─")
        self.btn_minimize.setObjectName("TitleBarButton")
        self.btn_minimize.setFixedSize(45, 35)
        self.btn_minimize.clicked.connect(self.minimize_window)
        layout.addWidget(self.btn_minimize)

        self.btn_maximize = QPushButton("□")
        self.btn_maximize.setObjectName("TitleBarButton")
        self.btn_maximize.setFixedSize(45, 35)
        self.btn_maximize.clicked.connect(self.maximize_restore_window)
        layout.addWidget(self.btn_maximize)

        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("TitleBarCloseButton")
        self.btn_close.setFixedSize(45, 35)
        self.btn_close.clicked.connect(self.close_window)
        layout.addWidget(self.btn_close)

        self._parent = parent
        self._start_pos = None
        
    def minimize_window(self):
        if self.window().isMinimized():
            self.window().showNormal()
        else:
            self.window().showMinimized()

    def maximize_restore_window(self):
        if self.window().isMaximized():
            self.window().showNormal()
            self.btn_maximize.setText("□")
        else:
            self.window().showMaximized()
            self.btn_maximize.setText("❐")

    def close_window(self):
        self.window().close()

    # Mouse events for dragging (Fallback if native move not used)
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self._start_pos:
            delta = event.globalPosition().toPoint() - self._start_pos
            self.window().move(self.window().pos() + delta)
            self._start_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self._start_pos = None
