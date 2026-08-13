from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtWidgets import QApplication, QMenu

from app.ui.qt.widgets.preview.layer_bbox.geometry import find_bbox_keys_intersecting_rect
from app.ui.qt.widgets.preview.layer_bbox.helpers import clamp_rect_to_pixmap
from app.ui.qt.widgets.preview.layer_bbox.layer_bbox import AnnotationOverlayWidget
from app.ui.qt.widgets.preview.layer_bbox.bbox_state import BBoxState
from app.ui.qt.widgets.preview.layer_bbox.menu import build_no_hit_action_map


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


def test_marquee_finds_intersecting_boxes() -> None:
    keys = find_bbox_keys_intersecting_rect(
        {
            "left": (10, 10, 30, 30),
            "right": (70, 10, 90, 30),
            "outside": (120, 10, 140, 30),
        },
        QRect(0, 0, 100, 100),
        QRect(0, 0, 200, 200),
        QSize(200, 200),
    )

    assert keys == ["left", "right"]


def test_empty_canvas_context_menu_includes_paste() -> None:
    app = QApplication.instance() or QApplication([])
    menu = QMenu()

    build_no_hit_action_map(menu)

    assert "Paste" in [action.text() for action in menu.actions()]
    app.quit()


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


def test_deselection_clears_stale_edit_handles() -> None:
    app = QApplication.instance() or QApplication([])
    overlay = AnnotationOverlayWidget()
    overlay.set_active_bboxes({"box-a": (10, 10, 30, 30)})
    overlay._editing_bbox_id = "box-a"
    overlay._state.rect = QRect(10, 10, 20, 20)

    overlay.set_selected_bbox_keys([])

    assert overlay._editing_bbox_id is None
    assert overlay._state.has_valid_rect is False
    app.quit()


def test_marquee_paints_without_runtime_errors() -> None:
    app = QApplication.instance() or QApplication([])
    overlay = AnnotationOverlayWidget()
    overlay.resize(100, 100)
    overlay._marquee_rect = QRect(10, 10, 50, 50)
    pixmap = QPixmap(100, 100)

    overlay.render(pixmap)

    assert not pixmap.isNull()
    app.quit()


def test_dragging_any_selected_box_emits_group_move() -> None:
    app = QApplication.instance() or QApplication([])
    overlay = AnnotationOverlayWidget()
    overlay.set_image_size(QSize(100, 100))
    overlay.set_pixmap_rect(QRect(0, 0, 100, 100))
    overlay.set_active_bboxes({"box-a": (10, 10, 30, 30), "box-b": (50, 50, 70, 70)})
    overlay.set_selected_bbox_keys(["box-a", "box-b"])
    moves: list[tuple[list[str], int, int]] = []
    overlay.bboxes_moved.connect(lambda keys, dx, dy: moves.append((keys, dx, dy)))

    overlay.mousePressEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPoint(60, 60),
            QPoint(60, 60),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    overlay.mouseMoveEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPoint(70, 60),
            QPoint(70, 60),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    overlay.mouseReleaseEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPoint(70, 60),
            QPoint(70, 60),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )

    assert len(moves) == 1
    assert set(moves[0][0]) == {"box-a", "box-b"}
    assert moves[0][1:] == (10, 0)
    app.quit()
