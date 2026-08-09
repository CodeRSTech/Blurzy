from __future__ import annotations

from PySide6.QtCore import Qt, QRect, QSize, Signal, QPointF
from PySide6.QtGui import QImage, QPainter, QColor, QPaintEvent, QResizeEvent
from PySide6.QtWidgets import QWidget


class VideoDisplayWidget(QWidget):
    pixmap_rect_changed = Signal(QRect, QSize)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._image: QImage | None = None
        self._pixmap_rect: QRect = QRect()
        self._placeholder_text: str = "No preview available"
        self._last_emitted: tuple[QRect, QSize] | None = None

        # --- Viewport Transform State ---
        self._zoom_factor: float = 1.0
        self._pan_offset: QPointF = QPointF(0.0, 0.0)

    # --- Viewport API ---
    def set_zoom(self, factor: float) -> None:
        self._zoom_factor = max(1.0, min(factor, 10.0))  # Clamp zoom between 1x and 10x
        self._update_pixmap_rect()
        self.update()

    def set_pan(self, dx: float, dy: float) -> None:
        self._pan_offset = QPointF(dx, dy)
        self._update_pixmap_rect()
        self.update()

    def reset_viewport(self) -> None:
        self._zoom_factor = 1.0
        self._pan_offset = QPointF(0.0, 0.0)
        self._update_pixmap_rect()
        self.update()

    # --- Existing API ---
    def set_image(self, image: QImage) -> None:
        self._image = image
        self._update_pixmap_rect()
        self.update()

    def set_message(self, message: str) -> None:
        self._image = None
        self._placeholder_text = message
        self._update_pixmap_rect()
        self.update()

    def get_pixmap_rect(self) -> QRect:
        return self._pixmap_rect

    # --- Rendering ---
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.fillRect(self.rect(), QColor(30, 30, 30))

        if self._image is not None:
            # We only draw the portion of the image that intersects the physical screen!
            painter.drawImage(self._pixmap_rect, self._image)
        else:
            painter.setPen(QColor(160, 160, 160))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, self._placeholder_text
            )

        painter.end()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_pixmap_rect()

    def _update_pixmap_rect(self) -> None:
        """Calculates the absolute position of the video on the screen, applying pan & zoom."""
        if self._image is None:
            new_rect = QRect()
            img_size = QSize()
        else:
            img_size = self._image.size()
            iw, ih = img_size.width(), img_size.height()
            ww, wh = self.width(), self.height()

            if iw == 0 or ih == 0 or ww == 0 or wh == 0:
                new_rect = QRect()
            else:
                # 1. Calculate Base Fit (Letterbox)
                base_scale = min(ww / iw, wh / ih)

                # 2. Apply Zoom Factor
                final_scale = base_scale * self._zoom_factor

                pw = int(iw * final_scale)
                ph = int(ih * final_scale)

                # 3. Calculate Base Origin (Centered)
                base_ox = (ww - pw) // 2
                base_oy = (wh - ph) // 2

                # 4. Apply Pan Offset
                ox = int(base_ox + self._pan_offset.x())
                oy = int(base_oy + self._pan_offset.y())

                new_rect = QRect(ox, oy, pw, ph)

        current_state = (new_rect, img_size)
        if self._last_emitted != current_state:
            self._pixmap_rect = new_rect
            self._last_emitted = current_state
            self.pixmap_rect_changed.emit(self._pixmap_rect, img_size)
