from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QAbstractButton
from PySide6.QtCore import Qt, QSize, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPixmap
from app.helpers import resource_path
from app.config.version import VERSION

class CaptionButton(QAbstractButton):
    """
    A custom button for window controls (Minimize, Maximize, Close)
    that draws high-quality icons using QPainter.
    """
    TypeMinimize = 0
    TypeMaximize = 1
    TypeClose = 2
    TypeRestore = 3

    def __init__(self, btn_type, parent=None):
        super().__init__(parent)
        self._type = btn_type
        self.setFixedSize(46, 32)
        self.setObjectName("CaptionButton")  # Default ID
        
        # Colors
        self._icon_color = QColor("#A1A1AA")
        self._hover_bg = QColor("#27272A")
        self._pressed_bg = QColor("#3F3F46")
        self._close_hover_bg = QColor("#E81123")
        self._close_pressed_bg = QColor("#B71C1C")
        self._close_icon_color = QColor("#FFFFFF")

        if self._type == self.TypeClose:
            self.setObjectName("CaptionCloseButton")

    def set_type(self, btn_type):
        self._type = btn_type
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw Background
        if self.isDown():
            bg_color = self._close_pressed_bg if self._type == self.TypeClose else self._pressed_bg
            painter.fillRect(self.rect(), bg_color)
        elif self.underMouse():
            bg_color = self._close_hover_bg if self._type == self.TypeClose else self._hover_bg
            painter.fillRect(self.rect(), bg_color)

        # Draw Icon
        icon_color = self._icon_color
        if self._type == self.TypeClose and (self.underMouse() or self.isDown()):
            icon_color = self._close_icon_color
        
        pen = QPen(icon_color)
        pen.setWidth(1)
        painter.setPen(pen)

        center_x = self.width() // 2
        center_y = self.height() // 2

        if self._type == self.TypeMinimize:
            # Draw horizontal line
            painter.drawLine(center_x - 5, center_y, center_x + 5, center_y)
        
        elif self._type == self.TypeMaximize:
            # Draw box
            painter.drawRect(center_x - 5, center_y - 5, 10, 10)
        
        elif self._type == self.TypeRestore:
            # Draw two overlapping boxes
            painter.drawRect(center_x - 3, center_y - 3, 8, 8) # Front
            # Back box (top-right lines)
            painter.drawLine(center_x + 1, center_y - 5, center_x + 5, center_y - 5) # Top
            painter.drawLine(center_x + 5, center_y - 5, center_x + 5, center_y + 1) # Right
        
        elif self._type == self.TypeClose:
            # Draw X
            painter.drawLine(center_x - 5, center_y - 5, center_x + 5, center_y + 5)
            painter.drawLine(center_x + 5, center_y - 5, center_x - 5, center_y + 5)


class TitleBar(QWidget):
    def __init__(self, parent=None, title="Application"):
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("TitleBar")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(8) # Buttons should touch

        # Logo
        self.logo_icon = QLabel()
        self.logo_icon.setFixedSize(20, 20)
        logo_pixmap = QPixmap(resource_path("app/resources/images/logo.png"))
        if not logo_pixmap.isNull():
            self.logo_icon.setPixmap(logo_pixmap.scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(self.logo_icon)

        # Title
        self.title_label = QLabel(f"{title} v{VERSION}")
        self.title_label.setObjectName("TitleBarTitle")
        layout.addWidget(self.title_label)

        layout.addStretch()

        # Window Controls
        self.btn_minimize = CaptionButton(CaptionButton.TypeMinimize, self)
        self.btn_minimize.clicked.connect(self.minimize_window)
        layout.addWidget(self.btn_minimize)

        self.btn_maximize = CaptionButton(CaptionButton.TypeMaximize, self)
        self.btn_maximize.clicked.connect(self.maximize_restore_window)
        layout.addWidget(self.btn_maximize)

        self.btn_close = CaptionButton(CaptionButton.TypeClose, self)
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
            self.btn_maximize.set_type(CaptionButton.TypeMaximize)
        else:
            self.window().showMaximized()
            self.btn_maximize.set_type(CaptionButton.TypeRestore)

    def close_window(self):
        self.window().close()

    # Mouse events for dragging
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