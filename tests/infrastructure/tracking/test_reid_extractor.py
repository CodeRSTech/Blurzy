from __future__ import annotations

import numpy as np

from app.domain.detection import BoxSource
from app.domain.views import BBoxViewModel
from app.infrastructure.tracking.reid_extractor import (
    PartBasedAppearanceEmbedder,
    cosine_distance,
    cosine_similarity,
    update_ema_embedding,
)


def _box(box_id: str, bbox: tuple[int, int, int, int]) -> BBoxViewModel:
    return BBoxViewModel(
        id=box_id,
        source=BoxSource.DETECTION,
        label="person",
        bbox_xyxy=bbox,
        color_hex="#ffffff",
        confidence=0.9,
        key=box_id,
    )


def test_embedder_returns_normalized_float32_vectors_for_all_dimensions():
    frame = np.full((160, 80, 3), (180, 60, 40), dtype=np.uint8)
    for dimension in (128, 256, 512):
        (embedding,) = PartBasedAppearanceEmbedder(dimension).extract_for_boxes(frame, [_box("a", (0, 0, 80, 160))])

        assert embedding is not None
        assert embedding.shape == (dimension,)
        assert embedding.dtype == np.float32
        np.testing.assert_allclose(np.linalg.norm(embedding), 1.0, atol=1e-6)


def test_embedder_handles_missing_frame_degenerate_and_clamped_boxes():
    embedder = PartBasedAppearanceEmbedder()
    frame = np.zeros((30, 30, 3), dtype=np.uint8)

    assert embedder.extract_for_boxes(None, [_box("a", (0, 0, 10, 10))]) == [None]
    results = embedder.extract_for_boxes(
        frame,
        [_box("small", (5, 5, 6, 15)), _box("outside", (40, 40, 50, 50)), _box("clamped", (-5, -5, 20, 20))],
    )
    assert results[0] is None
    assert results[1] is None
    assert results[2] is not None


def test_part_descriptor_separates_distinct_synthetic_appearance():
    first = np.zeros((128, 64, 3), dtype=np.uint8)
    first[:42] = (180, 40, 35)
    first[42:86] = (30, 60, 190)
    first[86:] = (35, 150, 50)
    same_subject = np.clip(first.astype(np.int16) + 8, 0, 255).astype(np.uint8)
    different_subject = np.zeros_like(first)
    different_subject[:42] = (30, 190, 180)
    different_subject[42:86] = (180, 40, 35)
    different_subject[86:] = (180, 150, 30)
    frame = np.concatenate((first, same_subject, different_subject), axis=1)
    boxes = [_box("a", (0, 0, 64, 128)), _box("b", (64, 0, 128, 128)), _box("c", (128, 0, 192, 128))]

    embeddings = PartBasedAppearanceEmbedder().extract_for_boxes(frame, boxes)
    assert all(vector is not None for vector in embeddings)
    assert cosine_similarity(embeddings[0], embeddings[1]) > 0.85
    assert cosine_similarity(embeddings[0], embeddings[2]) < 0.7


def test_cosine_and_ema_helpers_keep_vectors_normalized():
    first = np.asarray([1.0, 0.0], dtype=np.float32)
    second = np.asarray([0.0, 1.0], dtype=np.float32)

    assert cosine_similarity(first, first) == 1.0
    assert cosine_distance(first, second) == 1.0
    updated = update_ema_embedding(first, second)
    assert updated.dtype == np.float32
    np.testing.assert_allclose(np.linalg.norm(updated), 1.0, atol=1e-6)
