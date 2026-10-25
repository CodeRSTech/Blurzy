"""
Module for layer video; implements the Qt presentation components.

See Also:
    - [`PreviewContainer`][app.ui.qt.widgets.preview.preview_container.PreviewContainer] — embeds the video view with annotation overlays
    - [`PlaybackHandler`][app.ui.handlers.playback_handler.PlaybackHandler] — supplies playback updates

Layer: Presentation.
Context: Implements the qt presentation components at this architectural boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


from PySide6.QtCore import Qt, QRect, QSize, Signal, QPointF
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import QWidget
if TYPE_CHECKING:
    from PySide6.QtGui import QImage, QPaintEvent, QResizeEvent


class VideoDisplayWidget(QWidget):
    """
    Provide the video display widget presentation component.


    Args:
        parent: Optional Qt parent object.
    """
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
        """
        Set the display zoom, clamped to the range 1×–10×, and redraw.

        Args:
            factor: Requested zoom multiplier.
        """
        self._zoom_factor = max(1.0, min(factor, 10.0))  # Clamp zoom between 1x and 10x
        self._update_pixmap_rect()
        self.update()

    def set_pan(self, dx: float, dy: float) -> None:
        """
        Set the display offset in widget coordinates and redraw.

        Args:
            dx: Horizontal offset in pixels.
            dy: Vertical offset in pixels.
        """
        self._pan_offset = QPointF(dx, dy)
        self._update_pixmap_rect()
        self.update()

    def reset_viewport(self) -> None:
        """
        Restore 1× zoom and zero pan, then recompute and redraw the image.
        """
        self._zoom_factor = 1.0
        self._pan_offset = QPointF(0.0, 0.0)
        self._update_pixmap_rect()
        self.update()

    # --- Existing API ---
    def set_image(self, image: QImage) -> None:
        """
        Display an image, recompute its fitted rectangle, and redraw.

        Args:
            image: Image to display.
        """
        self._image = image
        self._update_pixmap_rect()
        self.update()

    def set_message(self, message: str) -> None:
        """
        Clear the image and display a centered placeholder message.

        Args:
            message: Text to show when no image is available.
        """
        self._image = None
        self._placeholder_text = message
        self._update_pixmap_rect()
        self.update()

    def get_pixmap_rect(self) -> QRect:
        """
        Return the image rectangle currently used for drawing.

        Returns:
            Current image rectangle in widget coordinates.
        """
        return self._pixmap_rect

    # --- Rendering ---
    def paintEvent(self, event: QPaintEvent) -> None:
        """
        Paint the current video frame or status message.

        Args:
            event: Qt event being handled. (QPaintEvent).
        """
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
        """
        Update the viewport after the widget is resized.

        Args:
            event: Qt event being handled. (QResizeEvent).
        """
        super().resizeEvent(event)
        self._update_pixmap_rect()

    def _update_pixmap_rect(self) -> None:
        """
        Calculates the absolute position of the video on the screen, applying pan & zoom.
        """
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
