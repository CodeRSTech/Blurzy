from __future__ import annotations

import numpy as np

from app.domain.detection import BoxSource
from app.domain.views import BBoxViewModel
from app.shared.masked_blur import apply_masked_blur, compute_blur_alpha_mask, overlay_alpha_mask


def test_alpha_mask_includes_box_interior_and_ten_pixel_outward_feather():
    box = BBoxViewModel(
        id="track-1",
        source=BoxSource.TRACKING_HUNGARIAN,
        label="person",
        bbox_xyxy=(10, 10, 20, 20),
        color_hex="#ffffff",
        confidence=0.9,
        key="track:1",
    )

    mask = compute_blur_alpha_mask((40, 40, 3), [box])

    assert mask.shape == (40, 40)
    assert mask[15, 15] == 1.0
    assert 0.0 < mask[15, 20] < 1.0
    assert mask[15, 29] == 0.0
    assert mask[15, 30] == 0.0


def test_mask_overlay_returns_highlighted_copy_without_mutating_original():
    frame = np.zeros((20, 20, 3), dtype=np.uint8)
    mask = np.zeros((20, 20), dtype=np.float32)
    mask[5:10, 5:10] = 1.0

    output = overlay_alpha_mask(frame, mask)

    assert np.all(frame == 0)
    assert np.any(output[6, 6] != 0)
    assert np.all(output[0, 0] == 0)


def test_mask_and_blur_cover_every_box_including_separate_and_overlapping_regions():
    boxes = [
        BBoxViewModel(
            id=f"box-{index}",
            source=BoxSource.TRACKING_HUNGARIAN,
            label="person",
            bbox_xyxy=coords,
            color_hex="#ffffff",
            confidence=0.9,
            key=f"track:{index}",
        )
        for index, coords in enumerate(
            [(10, 10, 40, 40), (70, 10, 100, 40), (85, 25, 115, 55), (10, 75, 40, 105)]
        )
    ]
    frame = np.random.default_rng(0).integers(0, 256, (128, 128, 3), dtype=np.uint8)
    original = frame.copy()
    mask = compute_blur_alpha_mask(frame.shape, boxes)
    highlighted = overlay_alpha_mask(frame, mask)
    blurred = apply_masked_blur(frame.copy(), boxes, strength=15)

    for box in boxes:
        x1, y1, x2, y2 = box.bbox_xyxy
        region = np.s_[y1:y2, x1:x2]
        assert np.all(mask[region] == 1.0)
        assert np.any(highlighted[region] != original[region])
        assert np.any(blurred[region] != original[region])
    np.testing.assert_array_equal(blurred[mask == 0], original[mask == 0])
    np.testing.assert_array_equal(frame, original)
