from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Property, QRect, QPoint
from PySide6.QtGui import QPixmap, QPainter

class SocialIcon(QLabel):
    def __init__(self, image_path, tooltip, size=24, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tooltip)
        
        # Load and store the original pixmap
        self._original_pixmap = QPixmap(image_path)
        if self._original_pixmap.isNull():
            self.setText("?")
        
        self._scale = 1.0
        
        # Setup Animation
        self._animation = QPropertyAnimation(self, b"iconScale", self)
        self._animation.setDuration(150) # ms
        self._animation.setEasingCurve(QEasingCurve.OutQuad)

        # Base Stylesheet for the circle background
        self.setStyleSheet(
            f"border-radius: {size//2}px; " 
            "background-color: #383838; "
            "border: 1px solid #555555;"
        )

    @Property(float)
    def iconScale(self):
        return self._scale

    @iconScale.setter
    def iconScale(self, value):
        self._scale = value
        self.update() # Trigger repaint

    def enterEvent(self, event):
        self._animation.stop()
        self._animation.setStartValue(self._scale)
        self._animation.setEndValue(1.2) # Zoom in 20%
        self._animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animation.stop()
        self._animation.setStartValue(self._scale)
        self._animation.setEndValue(1.0) # Return to normal
        self._animation.start()
        super().leaveEvent(event)

    def paintEvent(self, event):
        # Let the stylesheet draw the background/border first (handled by base QLabel paint if we don't override completely?)
        # Actually, standard QLabel paint might draw text if pixmap isn't set via setPixmap.
        # Since we are doing custom painting for the zoom, we should call standard paint for the background 
        # (via stylesheet) then draw our scaled image on top.
        
        # To let stylesheet background render, we can call standard paint, 
        # BUT standard paint attempts to draw content (text/pixmap).
        # Since we didn't setPixmap() on the label itself (we stored it in _original_pixmap),
        # calling super().paintEvent(event) will just draw the background styled by CSS.
        super().paintEvent(event)

        if self._original_pixmap.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.Antialiasing)

        # Calculate Scaled Size
        w = self.width()
        h = self.height()
        
        # Target size for the image inside the circle
        # 60% of the widget size gives a nice padding while keeping it large enough
        base_img_size = w * 0.60 
        
        current_img_size = base_img_size * self._scale
        
        # Center it: (Container - Content) / 2
        offset_x = (w - current_img_size) / 2
        offset_y = (h - current_img_size) / 2
        
        target_rect = QRect(int(offset_x), int(offset_y), int(current_img_size), int(current_img_size))
        
        painter.drawPixmap(target_rect, self._original_pixmap)
        painter.end()
