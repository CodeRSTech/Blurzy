"""Incremental DeepSORT-style tracking with conservative appearance memory."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np
from scipy.optimize import linear_sum_assignment

from app.domain.detection import BoxSource
from app.domain.views import BBoxViewModel
from app.infrastructure.tracking.tracking_strategy import uid_to_color

if TYPE_CHECKING:
    from app.domain.base.dtypes import ListOfBoxesByFrameIndexAsDict
    from app.infrastructure.dtypes import RGBFrame
    from app.infrastructure.tracking.reid_extractor import ReIDExtractorProtocol


def _xywh(box: BBoxViewModel) -> np.ndarray:
    x1, y1, x2, y2 = box.bbox_xyxy
    return np.asarray(((x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1), dtype=float)


def _iou(first: np.ndarray, second: np.ndarray) -> float:
    first_min, first_max = first[:2] - first[2:] / 2, first[:2] + first[2:] / 2
    second_min, second_max = second[:2] - second[2:] / 2, second[:2] + second[2:] / 2
    intersection = float(np.prod(np.maximum(0, np.minimum(first_max, second_max) - np.maximum(first_min, second_min))))
    union = float(np.prod(first[2:]) + np.prod(second[2:]) - intersection)
    return intersection / union if union > 0 else 0.0


def _normalize(vector: np.ndarray | None) -> np.ndarray | None:
    if vector is None:
        return None
    value = np.asarray(vector, dtype=np.float32)
    if value.ndim != 1 or value.size == 0 or not np.isfinite(value).all():
        raise ValueError("Embeddings must be finite, nonempty one-dimensional vectors.")
    norm = float(np.linalg.norm(value))
    return None if norm <= 1e-8 else value / norm


def _appearance_distance(track: _Track, vector: np.ndarray | None) -> float | None:
    if vector is None:
        return None
    prototypes = ([track.ema] if track.ema is not None else []) + list(track.gallery)
    if not prototypes:
        return None
    if any(prototype.shape != vector.shape for prototype in prototypes):
        raise ValueError("Embedding dimensions must stay consistent across frames.")
    return min(float(np.clip(1.0 - np.dot(prototype, vector), 0.0, 2.0)) for prototype in prototypes)


def _assign(cost: np.ndarray) -> list[tuple[int, int]]:
    if not cost.size:
        return []
    rows, columns = linear_sum_assignment(np.where(np.isfinite(cost), cost, 1e6))
    return [(int(row), int(column)) for row, column in zip(rows, columns) if np.isfinite(cost[row, column])]


def _legacy_embedding(box: BBoxViewModel) -> np.ndarray:
    """Build the historical batch-wrapper feature expected by DeepSORT."""
    x1, y1, x2, y2 = box.bbox_xyxy
    width, height = float(x2 - x1), float(y2 - y1)
    center_x, center_y = (float(x1 + x2) / 2, float(y1 + y2) / 2)
    confidence = float(box.confidence if box.confidence is not None else 1.0)
    label_hash = float(sum(ord(char) for char in box.label) % 97) / 97.0
    feature = np.asarray(
        [center_x, center_y, width, height, width * height, confidence, label_hash, 1.0],
        dtype=np.float32,
    )
    norm = float(np.linalg.norm(feature))
    return feature if norm == 0 else feature / norm


@dataclass
class _Track:
    uid: int
    label: str
    position: np.ndarray
    velocity: np.ndarray
    confidence: float
    last_seen: int
    last_observed_center: np.ndarray = field(default_factory=lambda: np.zeros(2, dtype=float))
    confirmed: bool = False
    hits: int = 1
    ema: np.ndarray | None = None
    gallery: deque[np.ndarray] = field(default_factory=lambda: deque(maxlen=30))

    @classmethod
    def create(cls, uid: int, box: BBoxViewModel, frame_idx: int) -> _Track:
        position = _xywh(box)
        return cls(
            uid=uid,
            label=box.label,
            position=_xywh(box),
            velocity=np.zeros(2, dtype=float),
            confidence=float(box.confidence if box.confidence is not None else 1.0),
            last_seen=frame_idx,
            last_observed_center=position[:2].copy(),
        )

    def predict(self, elapsed: int) -> None:
        self.position[:2] += self.velocity * elapsed
        self.position[2:] = np.maximum(self.position[2:], 1.0)

    def correct(self, box: BBoxViewModel, frame_idx: int, *, relocated: bool = False) -> None:
        observed = _xywh(box)
        elapsed = max(frame_idx - self.last_seen, 1)
        if relocated:
            self.velocity[:] = 0
        else:
            measured_velocity = (observed[:2] - self.last_observed_center) / elapsed
            self.velocity = 0.5 * self.velocity + 0.5 * measured_velocity
        self.position = observed
        self.last_observed_center = observed[:2].copy()
        self.confidence = float(box.confidence if box.confidence is not None else 1.0)
        self.last_seen = frame_idx
        self.hits += 1
        self.confirmed = self.confirmed or self.hits >= 2

    def remember(self, vector: np.ndarray) -> None:
        copied = vector.copy()
        self.gallery.append(copied)
        if self.ema is None:
            self.ema = copied
        else:
            blended = 0.90 * self.ema + 0.10 * copied
            self.ema = blended / max(float(np.linalg.norm(blended)), 1e-8)


class DeepSortStrategy:
    """Associate detections using motion, IoU, and bounded per-track Re-ID memory.

    Attributes:
        uses_appearance: Whether the strategy consumes appearance vectors.

    Embeddings align with ``frame_boxes`` and may be ``None``. If omitted while
    an RGB frame is supplied, the configured appearance extractor is used. Track
    memory is learned only from matched detections isolated by pairwise IoU <.25.

    Note:
        A track's appearance distance is the minimum cosine distance across its
        EMA prototype and its last 30 isolated detection embeddings.

    Example:
        strategy = DeepSortStrategy(min_iou=0.3)
    """

    uses_appearance = True

    def __init__(
        self,
        min_iou: float = 0.3,
        min_confidence: float = 0.1,
        confidence_decay: float = 0.05,
        *,
        max_age: int | None = None,
        appearance_extractor: ReIDExtractorProtocol | None = None,
    ) -> None:
        """Create an incremental tracker.

        Args:
            min_iou: Minimum overlap for the motion/IoU association stage.
            min_confidence: Minimum score to start a track and retain a coast.
            confidence_decay: Confidence loss per missed frame.
            max_age: Maximum missed frames; defaults to the decay-derived limit.
            appearance_extractor: Optional extractor used when ``frame`` is passed.

        Raises:
            ValueError: If thresholds are outside their valid ranges.
        Note:
            If the historical external DeepSORT backend is available, it is
            initialized only for compatibility with the legacy batch wrapper.

        Example:
            strategy = DeepSortStrategy(min_confidence=0.2)
        """
        if not 0 <= min_iou <= 1 or not 0 <= min_confidence <= 1:
            raise ValueError("min_iou and min_confidence must be between 0 and 1.")
        if not np.isfinite(confidence_decay) or confidence_decay < 0:
            raise ValueError("confidence_decay must be finite and nonnegative.")
        if max_age is not None and (not isinstance(max_age, int) or max_age < 0):
            raise ValueError("max_age must be a nonnegative integer.")
        self._min_iou = min_iou
        self._min_confidence = min_confidence
        self._confidence_decay = confidence_decay
        self._max_age = max_age if max_age is not None else max(1, int(round(1 / max(confidence_decay, 0.01))))
        self._extractor = appearance_extractor
        self._tracks: list[_Track] = []
        self._next_uid = 1
        self._last_frame: int | None = None
        self._embedding_dim: int | None = None
        self._legacy_engine: Any | None = None
        try:
            from deep_sort_realtime.deepsort_tracker import DeepSort  # pyright: ignore[reportMissingImports]
        except ModuleNotFoundError:
            pass
        else:
            # Kept solely for compatibility with callers of the historical batch API.
            self._legacy_engine = DeepSort(
                max_age=self._max_age,
                n_init=1,
                max_iou_distance=min(max(1.0 - min_iou, 0.05), 0.95),
                embedder=None,
            )

    @staticmethod
    def _isolated(index: int, boxes: Sequence[BBoxViewModel]) -> bool:
        position = _xywh(boxes[index])
        return all(_iou(position, _xywh(other)) < 0.25 for other_index, other in enumerate(boxes) if other_index != index)

    def _motion_matches(
        self,
        tracks: list[_Track],
        indices: list[int],
        boxes: Sequence[BBoxViewModel],
        vectors: list[np.ndarray | None],
    ) -> list[tuple[int, int]]:
        cost = np.full((len(tracks), len(indices)), np.inf)
        for row, track in enumerate(tracks):
            for column, index in enumerate(indices):
                if track.label != boxes[index].label:
                    continue
                overlap = _iou(track.position, _xywh(boxes[index]))
                distance = _appearance_distance(track, vectors[index])
                if overlap < self._min_iou and not (overlap > 0 and distance is not None and distance <= 0.28):
                    continue
                cost[row, column] = 1.0 - overlap if distance is None else 0.5 * (1.0 - overlap) + 0.5 * distance
        return [(row, indices[column]) for row, column in _assign(cost)]

    @staticmethod
    def _wide_reid_matches(
        tracks: list[_Track],
        indices: list[int],
        boxes: Sequence[BBoxViewModel],
        vectors: list[np.ndarray | None],
        frame_idx: int,
    ) -> list[tuple[int, int]]:
        distances = np.full((len(tracks), len(indices)), np.inf)
        for row, track in enumerate(tracks):
            for column, index in enumerate(indices):
                if track.label != boxes[index].label or vectors[index] is None:
                    continue
                position = _xywh(boxes[index])
                diagonal = max(float(np.linalg.norm(track.position[2:])), float(np.linalg.norm(position[2:])))
                elapsed = max(frame_idx - track.last_seen, 1)
                speed = float(np.linalg.norm(track.velocity))
                radius = 5.0 * diagonal + 3.0 * speed * elapsed
                if float(np.linalg.norm(track.position[:2] - position[:2])) > radius:
                    continue
                distance = _appearance_distance(track, vectors[index])
                if distance is not None and distance <= 0.28:
                    distances[row, column] = distance

        candidates = np.full_like(distances, np.inf)
        for row, column in zip(*np.where(np.isfinite(distances))):
            distance = distances[row, column]
            alternatives = np.concatenate((np.delete(distances[row], column), np.delete(distances[:, column], row)))
            if alternatives.size == 0 or float(np.min(alternatives)) - distance >= 0.08 - 1e-12:
                candidates[row, column] = distance
        return [(row, indices[column]) for row, column in _assign(candidates)]

    def update_frame(
        self,
        frame_idx: int,
        frame_boxes: Sequence[BBoxViewModel],
        frame: RGBFrame | None = None,
        embeddings: Sequence[np.ndarray | None] | None = None,
    ) -> list[BBoxViewModel]:
        """Advance one frame and return detection-backed and coasted track boxes.

        Args:
            frame_idx: Nonnegative, strictly increasing frame number.
            frame_boxes: Current detections in input order.
            frame: Optional RGB image for appearance extraction.
            embeddings: Optional vectors aligned with ``frame_boxes``.

        Returns:
            Active tracking boxes for this frame.

        Raises:
            ValueError: If frame indices, boxes, or embeddings are malformed.

        Note:
            Confirmed tracks are matched by age cascade, followed by unambiguous
            wide-radius appearance recovery and tentative-track IoU matching.

        Example:
            tracked_boxes = strategy.update_frame(0, detections, embeddings=vectors)
        """
        if not isinstance(frame_idx, int) or frame_idx < 0 or (
            self._last_frame is not None and frame_idx <= self._last_frame
        ):
            raise ValueError("frame_idx must be a nonnegative, strictly increasing integer.")
        for box in frame_boxes:
            position = _xywh(box)
            confidence = box.confidence if box.confidence is not None else 1.0
            if not np.isfinite(position).all() or np.any(position[2:] <= 0) or not 0 <= confidence <= 1:
                raise ValueError("Boxes must have finite positive dimensions and confidence in [0, 1].")
        if embeddings is None and frame is not None:
            if self._extractor is None:
                from app.infrastructure.tracking.reid_extractor import PartBasedAppearanceEmbedder

                self._extractor = PartBasedAppearanceEmbedder()
            embeddings = self._extractor.extract_for_boxes(frame, frame_boxes)
        if embeddings is not None and len(embeddings) != len(frame_boxes):
            raise ValueError("embeddings must contain one entry per input box.")
        vectors = [_normalize(value) for value in embeddings] if embeddings is not None else [None] * len(frame_boxes)
        dimensions = {vector.size for vector in vectors if vector is not None}
        if self._embedding_dim is not None:
            dimensions.add(self._embedding_dim)
        if len(dimensions) > 1:
            raise ValueError("Embedding dimensions must stay consistent across frames.")

        elapsed = frame_idx - self._last_frame if self._last_frame is not None else 1
        self._tracks = [
            track for track in self._tracks
            if frame_idx - track.last_seen - 1 <= self._max_age
            and track.confidence - (frame_idx - track.last_seen - 1) * self._confidence_decay >= self._min_confidence
        ]
        for track in self._tracks:
            track.predict(elapsed)
        self._last_frame = frame_idx
        if dimensions:
            self._embedding_dim = dimensions.pop()

        confirmed = [track for track in self._tracks if track.confirmed]
        unmatched_indices = list(range(len(frame_boxes)))
        matches: list[tuple[_Track, int, bool]] = []
        # DeepSORT's age cascade gives recently observed confirmed tracks first claim.
        for age in sorted({frame_idx - track.last_seen for track in confirmed}):
            cohort = [track for track in confirmed if frame_idx - track.last_seen == age]
            cohort_matches = self._motion_matches(cohort, unmatched_indices, frame_boxes, vectors)
            matched_ids = {cohort[row].uid for row, _ in cohort_matches}
            for row, index in cohort_matches:
                matches.append((cohort[row], index, False))
            unmatched_indices = [index for index in unmatched_indices if index not in {idx for _, idx in cohort_matches}]
            confirmed = [track for track in confirmed if track.uid not in matched_ids]

        recovery = self._wide_reid_matches(confirmed, unmatched_indices, frame_boxes, vectors, frame_idx)
        for row, index in recovery:
            matches.append((confirmed[row], index, True))
        unmatched_indices = [index for index in unmatched_indices if index not in {idx for _, idx in recovery}]

        tentative = [track for track in self._tracks if not track.confirmed]
        tentative_matches = self._motion_matches(tentative, unmatched_indices, frame_boxes, [None] * len(vectors))
        for row, index in tentative_matches:
            matches.append((tentative[row], index, False))
        unmatched_indices = [index for index in unmatched_indices if index not in {idx for _, idx in tentative_matches}]

        for track, index, relocated in matches:
            track.correct(frame_boxes[index], frame_idx, relocated=relocated)
            if vectors[index] is not None and self._isolated(index, frame_boxes):
                track.remember(vectors[index])
        for index in unmatched_indices:
            confidence = frame_boxes[index].confidence if frame_boxes[index].confidence is not None else 1.0
            if confidence < self._min_confidence:
                continue
            track = _Track.create(self._next_uid, frame_boxes[index], frame_idx)
            self._next_uid += 1
            if vectors[index] is not None and self._isolated(index, frame_boxes):
                track.remember(vectors[index])
            self._tracks.append(track)

        self._tracks = [
            track for track in self._tracks
            if frame_idx - track.last_seen <= self._max_age
            and track.confidence - (frame_idx - track.last_seen) * self._confidence_decay >= self._min_confidence
        ]
        output: list[BBoxViewModel] = []
        for track in self._tracks:
            age = frame_idx - track.last_seen
            center_x, center_y, width, height = track.position
            bbox = (
                int(round(center_x - width / 2)), int(round(center_y - height / 2)),
                int(round(center_x + width / 2)), int(round(center_y + height / 2)),
            )
            output.append(BBoxViewModel(
                id=f"track-{track.uid}",
                source=BoxSource.TRACKING_DEEPSORT,
                label=track.label,
                bbox_xyxy=bbox,
                color_hex=uid_to_color(track.uid),
                confidence=round(max(0.0, track.confidence - age * self._confidence_decay), 4),
                key=f"track:{track.uid}",
                detection_backed=age == 0,
                time_since_update=age,
            ))
        return output

    def track(
        self,
        source_data: ListOfBoxesByFrameIndexAsDict,
        total_frames: int = 0,
        *,
        frames: Mapping[int, np.ndarray] | Sequence[np.ndarray] | None = None,
        embeddings_by_frame: Mapping[int, Sequence[np.ndarray | None]] | None = None,
    ) -> ListOfBoxesByFrameIndexAsDict:
        """Track a full batch; the incremental API remains the implementation path.

        Args:
            source_data: Sparse per-frame detections.
            total_frames: Number of frames; zero infers it from ``source_data``.
            frames: Optional RGB frames keyed by index or supplied as a sequence.
            embeddings_by_frame: Optional aligned appearance vectors by frame.

        Returns:
            Track boxes keyed by frame index.

        Raises:
            ValueError: If the frame count is invalid.

        Note:
            When the historical DeepSORT backend is installed and optional
            appearance inputs are omitted, the batch wrapper preserves its old
            adapter behavior. Frame-aware callers use the native incremental
            association path.

        Example:
            tracked = strategy.track(detections, total_frames=120)

        When the optional historical ``deep_sort_realtime`` backend is available,
        this wrapper preserves its prior public behavior. Otherwise, it runs the
        native tracker over frames in order.
        """
        if not isinstance(total_frames, int) or total_frames < 0:
            raise ValueError("total_frames must be a nonnegative integer.")
        self._tracks = []
        self._next_uid = 1
        self._last_frame = None
        self._embedding_dim = None
        count = total_frames or (max(source_data) + 1 if source_data else 0)
        result: ListOfBoxesByFrameIndexAsDict = {}
        if self._legacy_engine is not None and frames is None and embeddings_by_frame is None:
            last_detection = max(source_data) if source_data else -1
            for frame_idx in range(count):
                boxes = source_data.get(frame_idx, [])
                raw = [
                    ([x1, y1, max(0, x2 - x1), max(0, y2 - y1)],
                     float(box.confidence if box.confidence is not None else 1.0), box.label)
                    for box in boxes
                    for x1, y1, x2, y2 in [box.bbox_xyxy]
                ]
                active = self._legacy_engine.update_tracks(
                    raw, embeds=[_legacy_embedding(box) for box in boxes], frame=None,
                )
                frame_output = []
                for track in active:
                    if hasattr(track, "is_confirmed") and not track.is_confirmed():
                        continue
                    uid = int(track.track_id)
                    age = int(getattr(track, "time_since_update", 0))
                    confidence = getattr(track, "det_conf", 1.0)
                    score = max(0.0, float(confidence if confidence is not None else 1.0) - age * self._confidence_decay)
                    if age and (age > self._max_age or score < self._min_confidence):
                        continue
                    left, top, right, bottom = track.to_ltrb()
                    label = getattr(track, "det_class", None) or "object"
                    frame_output.append(BBoxViewModel(
                        id=f"track-{uid}", source=BoxSource.TRACKING_DEEPSORT, label=str(label),
                        bbox_xyxy=(int(round(left)), int(round(top)), int(round(right)), int(round(bottom))),
                        color_hex=uid_to_color(uid), confidence=round(score, 4), key=f"track:{uid}",
                        detection_backed=age == 0, time_since_update=age,
                    ))
                if frame_idx > last_detection and not frame_output:
                    break
                result[frame_idx] = frame_output
            return result

        for frame_idx in range(count):
            frame = frames.get(frame_idx) if isinstance(frames, Mapping) else (
                frames[frame_idx] if frames is not None and frame_idx < len(frames) else None
            )
            result[frame_idx] = self.update_frame(
                frame_idx, source_data.get(frame_idx, []), frame=frame,
                embeddings=embeddings_by_frame.get(frame_idx) if embeddings_by_frame is not None else None,
            )
        return result
