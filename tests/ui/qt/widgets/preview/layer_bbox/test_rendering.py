from app.ui.qt.widgets.preview.layer_bbox.rendering import scale_bbox_border_width


def test_outline_width_scales_with_displayed_video_height() -> None:
    assert scale_bbox_border_width(2, 480) == 2
    assert scale_bbox_border_width(2, 720) == 3
    assert scale_bbox_border_width(2, 960) == 4


def test_outline_width_remains_visible_and_is_capped() -> None:
    assert scale_bbox_border_width(1, 120) == 1
    assert scale_bbox_border_width(10, 2160) == 12
    assert scale_bbox_border_width(3, 0) == 3
