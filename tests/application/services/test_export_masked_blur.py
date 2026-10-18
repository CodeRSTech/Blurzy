from __future__ import annotations

from unittest.mock import MagicMock

import cv2
import numpy as np
import pytest

from app.application.services.export_service import ExportService
from app.domain import BBoxViewModel, BoxSource, VideoDataLayer


def _box(coords: tuple[int, int, int, int]) -> BBoxViewModel:
    return BBoxViewModel("box", BoxSource.MANUAL, "person", coords, "#ffffff", 1.0)


def _frame() -> np.ndarray:
    return np.random.default_rng(42).integers(0, 256, (100, 140, 3), dtype=np.uint8)


@pytest.mark.parametrize("coords", [[], [(200, 0, 210, 10)], [(-20, -20, -5, -5)], [(5, 5, 5, 10)], [(20, 20, 10, 10)]])
def test_empty_or_outside_boxes_leave_frame_unchanged(coords):
    frame = _frame()
    original = frame.copy()

    result = ExportService._apply_masked_blur(frame, [_box(box) for box in coords], 15.0)

    assert result is frame
    np.testing.assert_array_equal(result, original)


@pytest.mark.parametrize("strength", [0.0, 15.0, 254.0, 255.0])
def test_box_interiors_match_one_full_frame_blur(strength):
    frame = _frame()
    original = frame.copy()
    expected = cv2.GaussianBlur(original, (max(3, int(strength) | 1),) * 2, 0)
    boxes = [_box((35, 25, 70, 65)), _box((55, 40, 85, 75))]

    result = ExportService._apply_masked_blur(frame, boxes, strength)

    assert result.dtype == original.dtype
    assert result.shape == original.shape
    np.testing.assert_array_equal(result[25:65, 35:70], expected[25:65, 35:70])
    np.testing.assert_array_equal(result[40:75, 55:85], expected[40:75, 55:85])


def test_duplicate_and_box_order_do_not_change_output():
    frame = _frame()
    first = _box((35, 25, 70, 65))
    second = _box((55, 40, 85, 75))

    expected = ExportService._apply_masked_blur(frame.copy(), [first, second], 15.0)
    reversed_boxes = ExportService._apply_masked_blur(frame.copy(), [second, first], 15.0)
    duplicated = ExportService._apply_masked_blur(frame.copy(), [first, second, first], 15.0)

    np.testing.assert_array_equal(reversed_boxes, expected)
    np.testing.assert_array_equal(duplicated, expected)


def test_feather_is_outward_and_leaves_pixels_beyond_ten_pixels_unchanged():
    frame = _frame()
    original = frame.copy()
    blurred = cv2.GaussianBlur(original, (15, 15), 0)

    result = ExportService._apply_masked_blur(frame, [_box((40, 30, 70, 60))], 15.0)

    np.testing.assert_array_equal(result[30:60, 40:70], blurred[30:60, 40:70])
    np.testing.assert_array_equal(result[:, :30], original[:, :30])
    np.testing.assert_array_equal(result[:, 79:], original[:, 79:])
    np.testing.assert_array_equal(result[:20], original[:20])
    np.testing.assert_array_equal(result[69:], original[69:])
    assert np.any(result[40, 35] != original[40, 35])
    assert np.any(result[40, 35] != blurred[40, 35])
    np.testing.assert_array_equal(result[40, 30], original[40, 30])


def test_clipped_boxes_use_half_open_coordinates():
    frame = _frame()
    expected = cv2.GaussianBlur(frame, (15, 15), 0)

    result = ExportService._apply_masked_blur(
        frame, [_box((-10, -5, 20, 25)), _box((120, 80, 160, 120))], 15.0
    )

    np.testing.assert_array_equal(result[:25, :20], expected[:25, :20])
    np.testing.assert_array_equal(result[80:, 120:], expected[80:, 120:])


def test_full_frame_box_and_tiny_frame_support_high_strength():
    frame = _frame()[:5, :7].copy()
    expected = cv2.GaussianBlur(frame, (255, 255), 0)

    result = ExportService._apply_masked_blur(frame, [_box((-10, -10, 100, 100))], 255.0)

    np.testing.assert_array_equal(result, expected)


def test_background_between_separated_boxes_stays_unchanged():
    frame = _frame()
    original = frame.copy()

    result = ExportService._apply_masked_blur(
        frame, [_box((10, 20, 25, 40)), _box((110, 60, 130, 80))], 15.0
    )

    np.testing.assert_array_equal(result[:, 40:95], original[:, 40:95])


def test_blurs_one_padded_roi_instead_of_each_box(monkeypatch):
    gaussian_blur = MagicMock(wraps=cv2.GaussianBlur)
    monkeypatch.setattr(cv2, "GaussianBlur", gaussian_blur)

    ExportService._apply_masked_blur(
        _frame(), [_box((35, 25, 50, 40)), _box((40, 30, 55, 45))], 15.0
    )

    gaussian_blur.assert_called_once()
    roi = gaussian_blur.call_args.args[0]
    assert roi.shape == (54, 54, 3)


@pytest.mark.parametrize("enabled,has_boxes", [(True, True), (False, True), (True, False)])
@pytest.mark.parametrize("draw_boxes", [False, True])
def test_render_loop_calls_masked_blur_once_and_preserves_writer_lifecycle(
    monkeypatch, enabled, has_boxes, draw_boxes
):
    frame = _frame()
    boxes = [_box((35, 25, 50, 40)), _box((40, 30, 55, 45))] if has_boxes else []
    session = MagicMock()
    session.state.metadata.frame_count = 1
    session.state.metadata.width = 140
    session.state.metadata.height = 100
    session.state.metadata.fps = 30.0
    session.state.settings.blur_enabled = enabled
    session.state.settings.blur_strength = 101.0
    session.state.settings.draw_boxes = draw_boxes
    session.video_reader.read_frame_at_index.return_value = frame
    session.data.get_boxes_for_layer_at_frame_index_as_list.return_value = boxes
    writer = MagicMock()
    writer.isOpened.return_value = True
    monkeypatch.setattr(cv2, "VideoWriter", MagicMock(return_value=writer))
    service = MagicMock()
    service._resolve_export_layer.return_value = VideoDataLayer.D
    service._apply_masked_blur.side_effect = ExportService._apply_masked_blur
    progress = MagicMock()

    ExportService._render_blurred_video(service, session, "output.mp4", progress)

    assert service._apply_masked_blur.call_count == int(enabled and has_boxes)
    if enabled and has_boxes:
        assert service._apply_masked_blur.call_args.args[1:] == (boxes, 101.0)
    writer.write.assert_called_once()
    expected = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    if enabled and has_boxes:
        ExportService._apply_masked_blur(expected, boxes, 101.0)
    np.testing.assert_array_equal(writer.write.call_args.args[0], expected)
    writer.release.assert_called_once()
    progress.assert_called_once_with(1, 1)
