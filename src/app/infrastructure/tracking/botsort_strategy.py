"""Incremental BoT-SORT-style tracking with conservative appearance updates.

Motion uses the constant-velocity state ``[cx, cy, w, h, vx, vy, vw, vh]``,
not aspect ratio. High-confidence boxes are associated by spatially gated
minimum IoU/appearance cost, then by an unambiguous wide-radius Re-ID pass.
Low-confidence boxes only recover existing tracks through motion. No
camera-motion compensation or learned model is needed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from scipy.optimize import linear_sum_assignment

from app.domain.detection import BoxSource
from app.domain.views import BBoxViewModel
from app.infrastructure.tracking.tracking_strategy import uid_to_color

if TYPE_CHECKING:
    from app.domain.base.dtypes import ListOfBoxesByFrameIndexAsDict
    from app.infrastructure.tracking.reid_extractor import ReIDExtractorProtocol


def _xywh(box: BBoxViewModel) -> np.ndarray:
    x1, y1, x2, y2 = box.bbox_xyxy
    return np.asarray([(x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1], dtype=float)


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    a_min, a_max = a[:2] - a[2:] / 2, a[:2] + a[2:] / 2
    b_min, b_max = b[:2] - b[2:] / 2, b[:2] + b[2:] / 2
    intersection = float(np.prod(np.maximum(0, np.minimum(a_max, b_max) - np.maximum(a_min, b_min))))
    union = float(np.prod(a[2:]) + np.prod(b[2:]) - intersection)
    return intersection / union if union > 0 else 0.0


def _normalize(vector: np.ndarray | None) -> np.ndarray | None:
    if vector is None:
        return None
    value = np.asarray(vector, dtype=float)
    if value.ndim != 1 or value.size == 0 or not np.isfinite(value).all():
        raise ValueError("Embeddings must be finite, nonempty one-dimensional vectors.")
    norm = float(np.linalg.norm(value))
    if norm <= 1e-8:
        return None
    return value / norm


def _cosine_distance(a: np.ndarray | None, b: np.ndarray | None) -> float | None:
    if a is None or b is None:
        return None
    if a.shape != b.shape:
        raise ValueError("Embedding dimensions must stay consistent across frames.")
    return float(np.clip(1.0 - np.dot(a, b), 0.0, 2.0))


def _assignment(cost: np.ndarray) -> list[tuple[int, int]]:
    if not cost.size:
        return []
    # Finite sentinels allow Hungarian assignment even with entirely gated rows.
    rows, columns = linear_sum_assignment(np.where(np.isfinite(cost), cost, 1e6))
    return [(int(row), int(col)) for row, col in zip(rows, columns) if np.isfinite(cost[row, col])]


@dataclass
class _Track:
    uid: int
    label: str
    mean: np.ndarray
    covariance: np.ndarray
    confidence: float
    last_seen: int
    appearance: np.ndarray | None = None

    @classmethod
    def create(cls, uid: int, box: BBoxViewModel, frame_idx: int) -> _Track:
        position = _xywh(box)
        scale = np.maximum(position[[2, 3, 2, 3]], 1.0)
        std = np.concatenate((0.1 * scale, 0.0625 * scale))
        return cls(
            uid,
            box.label,
            np.concatenate((position, np.zeros(4))),
            np.diag(std**2),
            float(box.confidence if box.confidence is not None else 1.0),
            frame_idx,
        )

    def predict(self) -> None:
        transition = np.eye(8)
        transition[:4, 4:] = np.eye(4)
        scale = np.maximum(self.mean[[2, 3, 2, 3]], 1.0)
        process_std = np.concatenate((0.05 * scale, 0.00625 * scale))
        self.mean = transition @ self.mean
        self.covariance = transition @ self.covariance @ transition.T + np.diag(process_std**2)
        self.mean[2:4] = np.maximum(self.mean[2:4], 1.0)

    def correct(self, box: BBoxViewModel, frame_idx: int, *, relocate: bool = False) -> None:
        if relocate:
            # A pure Re-ID relocation invalidates the old local velocity estimate.
            fresh = self.create(self.uid, box, frame_idx)
            self.mean, self.covariance = fresh.mean, fresh.covariance
        else:
            scale = np.maximum(self.mean[[2, 3, 2, 3]], 1.0)
            noise = np.diag((0.05 * scale) ** 2)
            innovation_covariance = self.covariance[:4, :4] + noise
            gain = np.linalg.solve(innovation_covariance, self.covariance[:4, :]).T
            self.mean += gain @ (_xywh(box) - self.mean[:4])
            residual = np.eye(8)
            residual[:, :4] -= gain
            self.covariance = residual @ self.covariance @ residual.T + gain @ noise @ gain.T
            self.mean[2:4] = np.maximum(self.mean[2:4], 1.0)
        self.confidence = float(box.confidence if box.confidence is not None else 1.0)
        self.last_seen = frame_idx


class BotSortStrategy:
    """Track boxes incrementally, with optional real appearance descriptors.

    Attributes:
        uses_appearance: Whether the strategy consumes appearance vectors.

    ``embeddings`` must align with the *original* frame_boxes order; ``None`` or
    zero vectors mean appearance is unavailable. Explicit embeddings take
    precedence over extraction from RGB ``frame`` pixels. Without either, the
    strategy operates on motion/IoU alone, never geometry-derived fake Re-ID.

    Tracks start only from scores >= max(0.5, min_confidence). Appearance EMA
    (90% history by default) is initialized/updated only on isolated high-score
    detections whose IoU with every other input box is strictly below 0.25.
    Coasting ends at max_age or when linearly decayed confidence falls below
    min_confidence. Frame indices must be nonnegative and strictly increasing.

    Re-ID requires cosine distance <= 0.25 and a >= 0.08 margin over competing
    tracks AND detections, within a radius scaled by box size, elapsed time, and
    track velocity. This recovery pass resets stale velocity after relocation.

    Note:
        The persistent motion state is ``[cx, cy, w, h, vx, vy, vw, vh]`` and
        appearance prototypes are updated only from isolated high-confidence
        observations.

    Example:
        strategy = BotSortStrategy(min_confidence=0.2)
    """

    uses_appearance: bool = True

    def __init__(
        self,
        min_iou: float = 0.3,
        min_confidence: float = 0.1,
        confidence_decay: float = 0.05,
        *,
        max_age: int = 30,
        ema_alpha: float = 0.9,
        appearance_extractor: ReIDExtractorProtocol | None = None,
    ) -> None:
        """Configure Kalman motion, confidence thresholds, and appearance memory.

        Args:
            min_iou: Minimum overlap required for local spatial association.
            min_confidence: Minimum confidence retained while coasting and used
                as the lower threshold for low-confidence recovery.
            confidence_decay: Confidence penalty per missed frame.
            max_age: Maximum number of missed frames before a track expires.
            ema_alpha: Weight of the previous appearance prototype.
            appearance_extractor: Optional replacement for the built-in extractor.

        Raises:
            ValueError: If a threshold, decay, age, or EMA weight is invalid.
        Note:
            The default appearance extractor is created lazily only when RGB
            frames are supplied without explicit embeddings.

        Example:
            strategy = BotSortStrategy(ema_alpha=0.9)
        """
        if not 0 <= min_iou <= 1 or not 0 <= min_confidence <= 1:
            raise ValueError("min_iou and min_confidence must be between 0 and 1.")
        if not np.isfinite(confidence_decay) or confidence_decay < 0:
            raise ValueError("confidence_decay must be finite and nonnegative.")
        if not isinstance(max_age, int) or max_age < 0 or not 0 <= ema_alpha < 1:
            raise ValueError("max_age must be a nonnegative integer and ema_alpha must be in [0, 1).")
        self._min_iou = min_iou
        self._min_confidence = min_confidence
        self._tau_high = max(0.5, min_confidence)
        self._confidence_decay = confidence_decay
        self._max_age = max_age
        self._ema_alpha = ema_alpha
        self._extractor = appearance_extractor
        self._tracks: list[_Track] = []
        self._next_uid = 1
        self._last_frame: int | None = None
        self._embedding_dim: int | None = None

    def _motion_matches(
        self,
        tracks: list[_Track],
        indices: list[int],
        boxes: Sequence[BBoxViewModel],
        vectors: list[np.ndarray | None],
        *,
        appearance: bool,
    ) -> list[tuple[int, int]]:
        cost = np.full((len(tracks), len(indices)), np.inf)
        for row, track in enumerate(tracks):
            for col, index in enumerate(indices):
                if track.label != boxes[index].label:
                    continue
                overlap = _iou(track.mean[:4], _xywh(boxes[index]))
                if overlap <= 0 or overlap < self._min_iou:
                    continue
                iou_distance = 1.0 - overlap
                cost[row, col] = iou_distance
                distance = _cosine_distance(track.appearance, vectors[index]) if appearance else None
                if distance is not None and distance <= 0.25 and iou_distance <= 1.0 - self._min_iou:
                    gated_appearance_distance = 0.5 * distance
                    cost[row, col] = min(iou_distance, gated_appearance_distance)
        return [(row, indices[col]) for row, col in _assignment(cost)]

    @staticmethod
    def _reid_matches(
        tracks: list[_Track],
        indices: list[int],
        boxes: Sequence[BBoxViewModel],
        vectors: list[np.ndarray | None],
        frame_idx: int,
    ) -> list[tuple[int, int]]:
        distances = np.full((len(tracks), len(indices)), np.inf)
        for row, track in enumerate(tracks):
            for col, index in enumerate(indices):
                position = _xywh(boxes[index])
                diagonal = max(float(np.linalg.norm(track.mean[2:4])), float(np.linalg.norm(position[2:])))
                elapsed = max(frame_idx - track.last_seen, 1)
                speed = float(np.linalg.norm(track.mean[4:6]))
                radius = 5.0 * diagonal + 3.0 * speed * elapsed
                if track.label != boxes[index].label or np.linalg.norm(track.mean[:2] - position[:2]) > radius:
                    continue
                distance = _cosine_distance(track.appearance, vectors[index])
                if distance is not None:
                    distances[row, col] = distance
        cost = np.full_like(distances, np.inf)
        for row in range(len(tracks)):
            for col in range(len(indices)):
                distance = distances[row, col]
                if distance > 0.25:
                    continue
                # Require a clear winner in BOTH directions, before assignment.
                alternatives = np.concatenate((np.delete(distances[row, :], col), np.delete(distances[:, col], row)))
                if alternatives.size and float(np.min(alternatives)) - distance < 0.08 - 1e-12:
                    continue
                cost[row, col] = distance
        return [(row, indices[col]) for row, col in _assignment(cost)]

    def update_frame(
        self,
        frame_idx: int,
        frame_boxes: Sequence[BBoxViewModel],
        frame: np.ndarray | None = None,
        embeddings: Sequence[np.ndarray | None] | None = None,
    ) -> list[BBoxViewModel]:
        """Advance to one frame and return observed and bounded coasted boxes.

        Args:
            frame_idx: Nonnegative, strictly increasing frame index.
            frame_boxes: Detections in the original input order.
            frame: Optional RGB frame for extractor fallback.
            embeddings: Optional vectors aligned with ``frame_boxes``.

        Returns:
            Tracking and coasted boxes for this frame.

        Raises:
            ValueError: If indices, boxes, embeddings, or embedding sizes are invalid.

        Note:
            Skipped frame indices age and predict tracks by the actual elapsed time.
            Low scores below ``min_confidence`` are ignored, but remain part of
            the same-frame appearance-isolation check.

        Example:
            boxes = strategy.update_frame(0, detections, embeddings=features)
        """
        if (
            not isinstance(frame_idx, int)
            or frame_idx < 0
            or (self._last_frame is not None and frame_idx <= self._last_frame)
        ):
            raise ValueError("frame_idx must be a nonnegative, strictly increasing integer.")
        for box in frame_boxes:
            position = _xywh(box)
            score = box.confidence if box.confidence is not None else 1.0
            if not np.isfinite(position).all() or np.any(position[2:] <= 0) or not 0 <= score <= 1:
                raise ValueError("Boxes must have finite positive dimensions and confidence in [0, 1].")
        if embeddings is None and frame is not None:
            if self._extractor is None:
                from app.infrastructure.tracking.reid_extractor import PartBasedAppearanceEmbedder

                self._extractor = PartBasedAppearanceEmbedder()
            embeddings = self._extractor.extract_for_boxes(frame, frame_boxes)
        if embeddings is not None and len(embeddings) != len(frame_boxes):
            raise ValueError("embeddings must contain one entry per input box.")
        vectors = [_normalize(vector) for vector in embeddings] if embeddings is not None else [None] * len(frame_boxes)
        dimensions = {vector.size for vector in vectors if vector is not None}
        if self._embedding_dim is not None:
            dimensions.add(self._embedding_dim)
        if len(dimensions) > 1:
            raise ValueError("Embedding dimensions must stay consistent across frames.")
        if dimensions:
            self._embedding_dim = dimensions.pop()

        elapsed = frame_idx - self._last_frame if self._last_frame is not None else 1
        self._tracks = [
            track
            for track in self._tracks
            if frame_idx - track.last_seen - 1 <= self._max_age
            and track.confidence - max(0, frame_idx - track.last_seen - 1) * self._confidence_decay
            >= self._min_confidence
        ]
        for track in self._tracks:
            for _ in range(elapsed):
                track.predict()
        self._last_frame = frame_idx

        high, low = [], []
        for index, box in enumerate(frame_boxes):
            score = box.confidence if box.confidence is not None else 1.0
            if score >= self._tau_high:
                high.append(index)
            elif score >= self._min_confidence:
                low.append(index)
        matches = self._motion_matches(self._tracks, high, frame_boxes, vectors, appearance=True)
        matched_rows = {row for row, _ in matches}
        matched_indices = {index for _, index in matches}
        remaining_rows = [row for row in range(len(self._tracks)) if row not in matched_rows]
        remaining_tracks = [self._tracks[row] for row in remaining_rows]
        reid = self._reid_matches(
            remaining_tracks,
            [index for index in high if index not in matched_indices],
            frame_boxes,
            vectors,
            frame_idx,
        )
        relocated = {remaining_rows[row] for row, _ in reid}
        matches.extend((remaining_rows[row], index) for row, index in reid)
        matched_rows.update(relocated)
        remaining_rows = [row for row in range(len(self._tracks)) if row not in matched_rows]
        motion_low = self._motion_matches(
            [self._tracks[row] for row in remaining_rows],
            low,
            frame_boxes,
            vectors,
            appearance=False,
        )
        matches.extend((remaining_rows[row], index) for row, index in motion_low)

        def update_appearance(track: _Track, index: int) -> None:
            vector = vectors[index]
            if index not in high or vector is None:
                return
            position = _xywh(frame_boxes[index])
            if any(_iou(position, _xywh(other)) >= 0.25 for j, other in enumerate(frame_boxes) if j != index):
                return
            track.appearance = (
                vector.copy()
                if track.appearance is None
                else _normalize(self._ema_alpha * track.appearance + (1 - self._ema_alpha) * vector)
            )

        for row, index in matches:
            track = self._tracks[row]
            track.correct(frame_boxes[index], frame_idx, relocate=row in relocated)
            update_appearance(track, index)
        matched_indices = {index for _, index in matches}
        for index in high:
            if index not in matched_indices:
                track = _Track.create(self._next_uid, frame_boxes[index], frame_idx)
                self._next_uid += 1
                update_appearance(track, index)
                self._tracks.append(track)

        self._tracks = [
            track
            for track in self._tracks
            if frame_idx - track.last_seen <= self._max_age
            and track.confidence - (frame_idx - track.last_seen) * self._confidence_decay >= self._min_confidence
        ]
        output = []
        for track in self._tracks:
            age = frame_idx - track.last_seen
            cx, cy, width, height = track.mean[:4]
            left, top = int(round(cx - width / 2)), int(round(cy - height / 2))
            bbox = (
                left,
                top,
                max(left + 1, int(round(cx + width / 2))),
                max(top + 1, int(round(cy + height / 2))),
            )
            output.append(
                BBoxViewModel(
                    id=f"track-{track.uid}",
                    source=BoxSource.TRACKING_BOTSORT,
                    label=track.label,
                    bbox_xyxy=bbox,
                    color_hex=uid_to_color(track.uid),
                    confidence=round(max(0.0, track.confidence - age * self._confidence_decay), 4),
                    key=f"track:{track.uid}",
                    detection_backed=age == 0,
                    time_since_update=age,
                )
            )
        return output

    def track(
        self,
        source_data: ListOfBoxesByFrameIndexAsDict,
        total_frames: int = 0,
        *,
        frames: Mapping[int, np.ndarray] | Sequence[np.ndarray] | None = None,
        embeddings_by_frame: Mapping[int, Sequence[np.ndarray | None]] | None = None,
    ) -> ListOfBoxesByFrameIndexAsDict:
        """Track a fresh batch by calling update_frame in chronological order.

        Args:
            source_data: Sparse per-frame detections.
            total_frames: Number of frames; zero infers it from ``source_data``.
            frames: Optional RGB frames keyed by index or supplied as a sequence.
            embeddings_by_frame: Optional per-frame, box-aligned feature vectors.

        Returns:
            Track boxes keyed by frame index.

        Raises:
            ValueError: If frame counts or source-data indices are invalid.

        Note:
            Each batch resets IDs and incremental state. Positive ``total_frames``
            includes trailing empty frames.

        Example:
            tracked = strategy.track(detections, total_frames=120)
        """
        if not isinstance(total_frames, int) or total_frames < 0:
            raise ValueError("total_frames must be a nonnegative integer.")
        if any(not isinstance(index, int) or index < 0 for index in source_data):
            raise ValueError("source_data frame indices must be nonnegative integers.")
        self._tracks = []
        self._next_uid = 1
        self._last_frame = None
        self._embedding_dim = None
        count = total_frames or (max(source_data) + 1 if source_data else 0)
        result: ListOfBoxesByFrameIndexAsDict = {}
        for index in range(count):
            frame = None
            if isinstance(frames, Mapping):
                frame = frames.get(index)
            elif frames is not None and index < len(frames):
                frame = frames[index]
            result[index] = self.update_frame(
                index,
                source_data.get(index, []),
                frame=frame,
                embeddings=embeddings_by_frame.get(index) if embeddings_by_frame is not None else None,
            )
        return result
