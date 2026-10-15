from __future__ import annotations

import numpy as np

from app.domain.detection import BoxSource
from app.domain.views import BBoxViewModel
from app.shared.masked_blur import compute_blur_alpha_mask, overlay_alpha_mask


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
