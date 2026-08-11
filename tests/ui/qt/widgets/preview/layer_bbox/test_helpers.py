from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from app.ui.qt.widgets.preview.layer_bbox.helpers import clamp_rect_to_pixmap
from app.ui.qt.widgets.preview.layer_bbox.layer_bbox import AnnotationOverlayWidget
from app.ui.qt.widgets.preview.layer_bbox.bbox_state import BBoxState


def test_zero_size_rect_is_not_considered_valid() -> None:
    state = BBoxState(rect=QRect(10, 20, 0, 0))

    assert state.has_valid_rect is False


def test_clamp_rect_to_pixmap_keeps_rect_inside_visible_bounds() -> None:
    rect = QRect(120, 90, 80, 60)
    pixmap_rect = QRect(50, 40, 100, 80)

    clamped = clamp_rect_to_pixmap(rect, pixmap_rect)

    assert clamped.left() >= pixmap_rect.left()
    assert clamped.top() >= pixmap_rect.top()
    assert clamped.right() <= pixmap_rect.right()
    assert clamped.bottom() <= pixmap_rect.bottom()
    assert clamped.size() == rect.size()


def test_overlay_rebases_active_rect_when_viewport_changes() -> None:
    app = QApplication.instance() or QApplication([])
    overlay = AnnotationOverlayWidget()

    overlay.set_image_size(QSize(100, 100))
    overlay.set_pixmap_rect(QRect(0, 0, 100, 100))
    overlay._state.rect = QRect(10, 10, 20, 20)

    overlay.set_pixmap_rect(QRect(50, 50, 200, 200))

    assert overlay._state.rect == QRect(70, 70, 39, 39)

    app.quit()


def test_panning_release_does_not_clear_active_selection() -> None:
    app = QApplication.instance() or QApplication([])
    overlay = AnnotationOverlayWidget()
    overlay._is_panning = True
    overlay._editing_bbox_id = "bbox-1"
    overlay._state.rect = QRect(10, 10, 20, 20)

    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPoint(0, 0),
        QPoint(0, 0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButtons(),
        Qt.KeyboardModifier.NoModifier,
    )
    overlay.mouseReleaseEvent(event)

    assert overlay._is_panning is False
    assert overlay._editing_bbox_id == "bbox-1"
    assert overlay._state.rect == QRect(10, 10, 20, 20)

    app.quit()
