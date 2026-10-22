"""Deterministic, part-based appearance embeddings for object tracking.

See Also:
    - [`DeepSortStrategy`][app.infrastructure.tracking.deepsort_strategy.DeepSortStrategy] — uses appearance features for association
    - [`BotSortStrategy`][app.infrastructure.tracking.botsort_strategy.BotSortStrategy] — uses appearance features for conservative re-identification

Layer: Infrastructure.
Context: Implements concrete processing and I/O behind application-facing contracts.
"""

from __future__ import annotations

from typing import Protocol, TYPE_CHECKING, Sequence

import cv2
import numpy as np

__all__ = [
    "ReIDExtractorProtocol",
    "PartBasedAppearanceEmbedder",
    "cosine_similarity",
    "cosine_distance",
    "update_ema_embedding",
]

if TYPE_CHECKING:
    from app.domain.views import BBoxViewModel
    from app.infrastructure.dtypes import RGBFrame


class ReIDExtractorProtocol(Protocol):
    """Interface for extracting one optional appearance vector per box.

    Note:
        Implementations may use a hand-crafted descriptor or a learned backbone;
        callers rely only on input-order preservation and unit-normalized vectors.


Layer: Infrastructure.
Context: Implements concrete processing or I/O behind application-facing contracts.
"""

    def extract_for_boxes(
        self,
        frame: RGBFrame | None,
        boxes: Sequence[BBoxViewModel],
    ) -> list[np.ndarray | None]:
        """Extract embeddings aligned with `boxes`, using `None` for invalid crops.

        Args:
            frame: RGB image for the current video frame, or `None` when unavailable.
            boxes: Bounding boxes in frame pixel coordinates.

        Returns:
            A list with one normalized float32 vector or `None` per input box.

        Raises:
            ValueError: If an implementation receives malformed frame data.

        Note:
            Result positions must correspond exactly to the input box positions.

        Example:
            vectors = extractor.extract_for_boxes(frame, boxes)
        """
        ...


class PartBasedAppearanceEmbedder:
    """Build compact, illumination-tolerant color and texture descriptors.

    Attributes:
        embedding_dim: Requested output size; supported values are 128, 256, and 512.

    Note:
        Each crop is resized to a canonical 64-by-128 grid. HSV and CIE-LAB
        histograms encode chromatic appearance while Sobel orientation
        histograms preserve local texture and edge structure. The 128 mode
        prioritizes speed, 256 adds a center-weighted core, and 512 uses a
        six-region spatial pyramid.

    Example:
        embedder = PartBasedAppearanceEmbedder(embedding_dim=256)


Layer: Infrastructure.
Context: Implements concrete processing or I/O behind application-facing contracts.
"""

    _CANONICAL_SIZE = (64, 128)

    def __init__(self, embedding_dim: int = 256) -> None:
        """Initialize the descriptor at one of the supported output dimensions.

        Args:
            embedding_dim: Output dimension, either 128, 256, or 512.

        Raises:
            ValueError: If the requested dimension is unsupported.
        Note:
            No learned weights or network downloads are required.

        Example:
            embedder = PartBasedAppearanceEmbedder(embedding_dim=128)
        """
        if embedding_dim not in (128, 256, 512):
            raise ValueError("embedding_dim must be one of 128, 256, or 512.")
        self.embedding_dim = embedding_dim

    def extract_for_boxes(
        self,
        frame: RGBFrame | None,
        boxes: Sequence[BBoxViewModel],
    ) -> list[np.ndarray | None]:
        """Extract an appearance descriptor for every usable box crop.

        Args:
            frame: RGB image for the current frame, or `None`.
            boxes: Boxes to crop in their original input order.

        Returns:
            Unit-normalized float32 vectors, or `None` for invalid crops.

        Raises:
            ValueError: If the input frame does not have an RGB array shape.

        Note:
            Coordinates are clamped before cropping, and crops smaller than
            two pixels in either dimension are rejected.

        Example:
            vectors = embedder.extract_for_boxes(frame, detections)
        """
        if frame is None:
            return [None for _ in boxes]
        if frame.ndim != 3 or frame.shape[2] != 3 or frame.dtype != np.uint8:
            raise ValueError("frame must be an HxWx3 uint8 RGB array.")

        height, width = frame.shape[:2]
        result: list[np.ndarray | None] = []
        for box in boxes:
            x1, y1, x2, y2 = box.bbox_xyxy
            left = max(0, min(width, int(x1)))
            top = max(0, min(height, int(y1)))
            right = max(0, min(width, int(x2)))
            bottom = max(0, min(height, int(y2)))
            if right - left < 2 or bottom - top < 2:
                result.append(None)
                continue

            crop = frame[top:bottom, left:right]
            if crop.size == 0:
                result.append(None)
                continue

            canonical = cv2.resize(
                crop,
                self._CANONICAL_SIZE,
                interpolation=cv2.INTER_AREA if crop.shape[1] >= 64 and crop.shape[0] >= 128 else cv2.INTER_LINEAR,
            )
            result.append(self._describe(canonical))
        return result

    def _describe(self, rgb_crop: np.ndarray) -> np.ndarray:
        """Build and normalize the configured multi-region descriptor."""
        hsv = cv2.cvtColor(rgb_crop, cv2.COLOR_RGB2HSV)
        lab = cv2.cvtColor(rgb_crop, cv2.COLOR_RGB2LAB)
        gray = cv2.cvtColor(rgb_crop, cv2.COLOR_RGB2GRAY)
        grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        magnitude, angle = cv2.cartToPolar(grad_x, grad_y, angleInDegrees=True)
        coarse_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=5)
        coarse_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=5)
        coarse_magnitude, coarse_angle = cv2.cartToPolar(coarse_x, coarse_y, angleInDegrees=True)

        if self.embedding_dim == 128:
            hsv_regions = [hsv[0:43, :], hsv[43:86, :], hsv[86:128, :]]
            texture_regions = [
                (magnitude[0:43, :], angle[0:43, :]),
                (magnitude[43:86, :], angle[43:86, :]),
                (magnitude[86:128, :], angle[86:128, :]),
            ]
            features = [
                np.concatenate((self._color_hist(region, 0, (8, 4, 2)), self._gradient_hist(*texture, bins=8)))
                for region, texture in zip(hsv_regions, texture_regions)
            ]
            descriptor = np.concatenate(features)
            descriptor = self._resize_feature(descriptor, self.embedding_dim)
        elif self.embedding_dim == 256:
            # The center core narrows the crop horizontally to down-weight clutter
            # at both box edges while retaining the three full-width body strips.
            regions = [
                (slice(0, 43), slice(0, 64)),
                (slice(43, 86), slice(0, 64)),
                (slice(86, 128), slice(0, 64)),
                (slice(16, 112), slice(16, 48)),
            ]
            descriptor_parts: list[np.ndarray] = []
            for y_slice, x_slice in regions:
                hpart = hsv[y_slice, x_slice]
                lpart = lab[y_slice, x_slice]
                mpart = magnitude[y_slice, x_slice]
                apart = angle[y_slice, x_slice]
                descriptor_parts.append(
                    np.concatenate(
                        (
                            self._color_hist(hpart, 0, (8, 2, 2)),
                            self._color_hist(lpart, 1, (4, 2, 2)),
                            self._gradient_hist(mpart, apart, bins=16),
                        )
                    )
                )
            descriptor = np.concatenate(descriptor_parts)
        else:
            descriptor_parts = []
            # A 2-by-3 spatial pyramid distinguishes upper, middle, and lower
            # colors and textures while keeping each cell's histogram normalized.
            for row in range(3):
                y0, y1 = row * 128 // 3, (row + 1) * 128 // 3
                for col in range(2):
                    x0, x1 = col * 32, (col + 1) * 32
                    descriptor_parts.append(
                        np.concatenate(
                            (
                                self._color_hist(hsv[y0:y1, x0:x1], 0, (8, 2, 2)),
                                self._color_hist(lab[y0:y1, x0:x1], 1, (4, 2, 2)),
                                self._gradient_hist(magnitude[y0:y1, x0:x1], angle[y0:y1, x0:x1], bins=16),
                                self._gradient_hist(
                                    coarse_magnitude[y0:y1, x0:x1],
                                    coarse_angle[y0:y1, x0:x1],
                                    bins=16,
                                ),
                            )
                        )
                    )
            descriptor = np.concatenate(descriptor_parts)
            descriptor = self._resize_feature(descriptor, self.embedding_dim)

        descriptor = np.asarray(descriptor, dtype=np.float32)
        norm = float(np.linalg.norm(descriptor))
        if norm <= 1e-8:
            return np.zeros(self.embedding_dim, dtype=np.float32)
        return descriptor / norm

    @staticmethod
    def _hist(image: np.ndarray, color_space: int, bins: tuple[int, int, int]) -> np.ndarray:
        """Return an L1-normalized three-channel spatial color histogram."""
        channel_ranges = (0, 180, 0, 256, 0, 256) if color_space == 0 else (0, 256, 0, 256, 0, 256)
        hist = cv2.calcHist([image], [0, 1, 2], None, list(bins), list(channel_ranges))
        hist = cv2.normalize(hist, None, alpha=1.0, norm_type=cv2.NORM_L1)
        return hist.reshape(-1).astype(np.float32)

    @classmethod
    def _color_hist(cls, image: np.ndarray, color_space: int, bins: tuple[int, int, int]) -> np.ndarray:
        """Down-weight HSV value and Lab lightness while retaining chroma."""
        histogram = cls._hist(image, color_space, bins).reshape(bins)
        if color_space == 0:
            histogram *= np.linspace(1.0, 0.35, num=bins[2], dtype=np.float32)[None, None, :]
        else:
            histogram *= np.linspace(0.35, 1.0, num=bins[0], dtype=np.float32)[:, None, None]
        return histogram.reshape(-1)

    @staticmethod
    def _gradient_hist(magnitude: np.ndarray, angle: np.ndarray, *, bins: int) -> np.ndarray:
        """Compute a magnitude-weighted histogram of unsigned Sobel orientations."""
        orientation = np.mod(angle, 180.0)
        hist, _ = np.histogram(
            orientation,
            bins=bins,
            range=(0.0, 180.0),
            weights=np.maximum(magnitude, 0.0),
        )
        hist = hist.astype(np.float32)
        total = float(hist.sum())
        return hist / total if total > 1e-8 else hist

    @staticmethod
    def _resize_feature(feature: np.ndarray, output_size: int) -> np.ndarray:
        """Interpolate a fixed descriptor layout to a requested vector size."""
        if feature.size == output_size:
            return feature.astype(np.float32, copy=False)
        source = np.linspace(0.0, 1.0, num=feature.size, dtype=np.float32)
        target = np.linspace(0.0, 1.0, num=output_size, dtype=np.float32)
        return np.interp(target, source, feature).astype(np.float32)


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    r"""Return cosine similarity for two equal-length vectors.

    Args:
        vec_a: First feature vector.
        vec_b: Second feature vector.

    Returns:
        Cosine similarity clamped to the range `[-1, 1]`.

    Raises:
        ValueError: If the vectors have different shapes.

    Note:
        For nonzero inputs, similarity is

        $$
        \operatorname{sim}(\mathbf{a},\mathbf{b}) =
        \operatorname{clip}\!\left(
        \frac{\mathbf{a}^{\mathsf T}\mathbf{b}}
        {\lVert\mathbf{a}\rVert_2\lVert\mathbf{b}\rVert_2},-1,1\right).
        $$

        If either input norm is at most $10^{-8}$, the implementation returns
        zero instead of dividing by zero.

    Example:
        similarity = cosine_similarity(first, second)
    """
    if vec_a.shape != vec_b.shape:
        raise ValueError("cosine similarity vectors must have matching shapes.")
    norm_a = float(np.linalg.norm(vec_a))
    norm_b = float(np.linalg.norm(vec_b))
    if norm_a <= 1e-8 or norm_b <= 1e-8:
        return 0.0
    return float(np.clip(np.dot(vec_a, vec_b) / (norm_a * norm_b), -1.0, 1.0))


def cosine_distance(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    r"""Return cosine distance, defined as one minus cosine similarity.

    Args:
        vec_a: First feature vector.
        vec_b: Second feature vector.

    Returns:
        A distance in `[0, 2]`.

    Raises:
        ValueError: If the vectors have different shapes.

    Note:
        The implementation uses
        $d_{\cos}(\mathbf{a},\mathbf{b}) =
        1-\operatorname{sim}(\mathbf{a},\mathbf{b})$. For unit-normalized
        nonzero vectors, this reduces to
        $1-\mathbf{a}^{\mathsf T}\mathbf{b}$. If either input norm is at most
        $10^{-8}$, the similarity fallback is zero and the distance is one.

    Example:
        distance = cosine_distance(first, second)
    """
    return 1.0 - cosine_similarity(vec_a, vec_b)


def update_ema_embedding(
    prototype: np.ndarray | None,
    new_vec: np.ndarray,
    momentum: float = 0.90,
) -> np.ndarray:
    r"""Blend a new unit feature into a normalized exponential-moving prototype.

    Args:
        prototype: Prior normalized appearance vector, if any.
        new_vec: Newly observed appearance vector.
        momentum: Weight assigned to the existing prototype in `[0, 1)`.

    Returns:
        A normalized float32 vector.

    Raises:
        ValueError: If momentum or vector shapes are invalid.

    Note:
        For prior prototype $\mathbf{p}$, observation $\mathbf{x}$, and
        momentum $m$, the blend and normalized update are

        $$
        \mathbf{b} =
        \begin{cases}
        \mathbf{x}, & \mathbf{p}\text{ is absent},\\
        m\mathbf{p} + (1-m)\mathbf{x}, & \text{otherwise},
        \end{cases}
        \qquad
        \mathbf{p}_{\mathrm{new}} =
        \frac{\mathbf{b}}{\max(\lVert\mathbf{b}\rVert_2,10^{-8})}.
        $$

        Inputs are converted to float32; an existing prototype is expected to
        already be normalized. The denominator's epsilon floor prevents division
        by zero.

    Example:
        prototype = update_ema_embedding(previous, observation, momentum=0.9)
    """
    if not 0.0 <= momentum < 1.0:
        raise ValueError("momentum must be in the range [0, 1).")
    new_vec = np.asarray(new_vec, dtype=np.float32)
    if prototype is None:
        blended = new_vec.copy()
    else:
        if prototype.shape != new_vec.shape:
            raise ValueError("EMA embedding vectors must have matching shapes.")
        blended = momentum * np.asarray(prototype, dtype=np.float32) + (1.0 - momentum) * new_vec
    norm = float(np.linalg.norm(blended))
    return blended / max(norm, 1e-8)
