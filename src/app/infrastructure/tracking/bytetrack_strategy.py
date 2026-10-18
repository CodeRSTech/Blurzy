"""ByteTrack strategy adapter.

Simple explanation:
ByteTrack links boxes from one frame to the next by looking at overlap and
motion, then keeps each object under the same track ID. If a detection is not
very confident, ByteTrack can still use it as a secondary hint so tracks do not
break too quickly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


from types import SimpleNamespace


import numpy as np


from app.domain.detection import BoxSource
from app.domain.views import BBoxViewModel
from app.infrastructure.tracking.tracking_strategy import uid_to_color
from app.shared.logging_cfg import get_logger
if TYPE_CHECKING:
    from typing import Sequence
    from typing import Any
    from app.domain.base.dtypes import ListOfBoxesByFrameIndexAsDict
    from app.infrastructure.dtypes import RGBFrame


logger = get_logger("Infrastructure->Tracking->ByteTrackStrategy")


def _as_xyxy_int(bbox: Any) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    return int(round(float(x1))), int(round(float(y1))), int(round(float(x2))), int(round(float(y2)))


def _generalized_iou(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
) -> float:
    """Calculate generalized intersection-over-union for two xyxy boxes.

    Args:
        first: Predicted track box.
        second: Current detection box.

    Returns:
        GIoU in the range ``[-1.0, 1.0]``.

    Example:
        similarity = _generalized_iou(predicted, detection)
    """
    x1 = max(first[0], second[0])
    y1 = max(first[1], second[1])
    x2 = min(first[2], second[2])
    y2 = min(first[3], second[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area_first = max(0, first[2] - first[0]) * max(0, first[3] - first[1])
    area_second = max(0, second[2] - second[0]) * max(0, second[3] - second[1])
    union = area_first + area_second - intersection
    if union <= 0:
        return -1.0
    enclosing_x1 = min(first[0], second[0])
    enclosing_y1 = min(first[1], second[1])
    enclosing_x2 = max(first[2], second[2])
    enclosing_y2 = max(first[3], second[3])
    enclosing = max(1, enclosing_x2 - enclosing_x1) * max(
        1, enclosing_y2 - enclosing_y1
    )
    iou = intersection / union
    return iou - (enclosing - union) / enclosing


class ByteTrackStrategy:
    """Track objects using ByteTrack while preserving the app's output contract.

    Simple runtime note:
    Ultralytics ByteTrack expects a ``Boxes``/results-like object (with fields
    like ``conf`` and ``xywh``), not a raw matrix. We therefore build a
    ``Boxes`` object per frame and parse ByteTrack's ndarray output rows back
    into ``BBoxViewModel`` objects.
    """

    uses_appearance = False

    def __init__(
        self,
        min_iou: float = 0.3,
        min_confidence: float = 0.1,
        min_detection_confidence: float = 0.25,
        confidence_decay: float = 0.05,
    ) -> None:
        """Initialize ByteTrack and app-side labels and coast confidence.

        Args:
            min_iou: IoU similarity used to configure tracker association.
            min_confidence: Minimum confidence for accepting tracker output.
            min_detection_confidence: Confidence floor applied before tracking.
            confidence_decay: Confidence reduction per coasted frame.
        Raises:
            ModuleNotFoundError: If the optional Ultralytics dependency is unavailable.

        Note:
            The wrapped ByteTrack constructor is version-adapted because supported
            releases differ in their required constructor arguments.

        Example:
            strategy = ByteTrackStrategy(min_iou=0.3, confidence_decay=0.05)
        """
        try:
            from ultralytics.trackers.byte_tracker import BYTETracker  # pyright: ignore[reportMissingImports]
            from ultralytics.engine.results import Boxes  # pyright: ignore[reportMissingImports]
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "ByteTrack strategy requires 'ultralytics'. Install dependencies to use strategy='bytetrack'."
            ) from exc

        self._boxes_cls = Boxes
        self._confidence_decay = confidence_decay
        self._min_confidence = min_confidence
        self._min_detection_confidence = min_detection_confidence
        self._label_to_id: dict[str, int] = {}
        self._id_to_label: dict[int, str] = {}
        self._uid_aliases: dict[int, int] = {}
        self._motion_state: dict[
            int,
            tuple[int, tuple[int, int, int, int], float, float, float, float, str],
        ] = {}
        self._next_synthetic_uid = -1

        tracker_args = SimpleNamespace(
            track_high_thresh=0.5,
            track_low_thresh=min(min_confidence, min_detection_confidence, 0.10),
            new_track_thresh=0.5,
            track_buffer=30,
            match_thresh=min(max(min_iou, 0.1), 0.95),
            fuse_score=True,
        )
        self._tracker_args = tracker_args
        # ByteTrack constructor signatures differ across releases.
        try:
            self._engine = BYTETracker(tracker_args, 30)
        except TypeError:
            self._engine = BYTETracker(tracker_args)

    def _class_id_for_label(self, label: str) -> int:
        if label not in self._label_to_id:
            next_id = len(self._label_to_id)
            self._label_to_id[label] = next_id
            self._id_to_label[next_id] = label
        return self._label_to_id[label]

    def update_frame(
        self,
        frame_idx: int,
        frame_boxes: list[BBoxViewModel],
        frame: RGBFrame | None = None,
        embeddings: Sequence[np.ndarray | None] | None = None,
    ) -> list[BBoxViewModel]:
        """Update ByteTrack with one frame of detections.

        Args:
            frame_idx: Zero-based frame index.
            frame_boxes: Detections to associate for this frame.
            frame: Optional RGB frame; unused by this motion-only strategy.
            embeddings: Optional box-aligned features; unused here.

        Returns:
            Detection-backed or coasted track boxes for this frame.
        """
        if frame_idx == 0:
            self._label_to_id.clear()
            self._id_to_label.clear()
            self._last_seen_by_track: dict[int, int] = {}
            self._uid_aliases.clear()
            self._motion_state.clear()
            self._next_synthetic_uid = -1
        det_rows = [
            [
                *item.bbox_xyxy,
                float(item.confidence if item.confidence is not None else 1.0),
                float(self._class_id_for_label(item.label)),
            ]
            for item in frame_boxes
        ]
        det_arr = np.asarray(det_rows, dtype=np.float32) if det_rows else np.empty((0, 6), dtype=np.float32)
        # Bound Stage 2 by session filters while retaining the requested 0.10 cap.
        tau_low = min(
            self._min_confidence,
            self._min_detection_confidence,
            0.10,
        )
        if det_rows:
            median_frame_confidence = float(
                np.median(
                    [
                        float(item.confidence if item.confidence is not None else 1.0)
                        for item in frame_boxes
                    ]
                )
            )
            # Keep the frame median in Stage 1 while routing weaker scores lower.
            tau_high = round(
                max(tau_low + 0.05, min(0.50, median_frame_confidence - 0.05)),
                4,
            )
        else:
            # Empty frames cannot associate detections; retain a valid split for
            # the next update without deriving a median from an empty array.
            tau_high = max(tau_low + 0.05, 0.50)
        self._tracker_args.track_low_thresh = tau_low
        self._tracker_args.track_high_thresh = tau_high
        self._tracker_args.new_track_thresh = tau_high
        engine_args = getattr(self._engine, "args", None)
        if engine_args is not None and hasattr(engine_args, "track_high_thresh"):
            engine_args.track_low_thresh = tau_low
            engine_args.track_high_thresh = tau_high
            engine_args.new_track_thresh = tau_high
        boxes = self._boxes_cls(det_arr, (1, 1))
        active_tracks = self._engine.update(boxes)
        frame_output: list[BBoxViewModel] = []
        seen_detection_indices: set[int] = set()
        detection_track_ids: set[int] = set()
        for row in active_tracks if getattr(active_tracks, "size", 0) else []:
            det_idx = int(row[7]) if len(row) > 7 else -1
            engine_uid = int(row[4])
            detection_backed = 0 <= det_idx < len(frame_boxes)
            bbox = _as_xyxy_int(row[:4])
            cls_id = int(row[6]) if len(row) > 6 else -1
            label = self._id_to_label.get(cls_id, f"class-{cls_id}")
            if detection_backed and engine_uid not in self._uid_aliases:
                fallback_uid = self._best_fallback_track(
                    frame_idx,
                    bbox,
                    label,
                    excluded_ids=detection_track_ids | {engine_uid},
                )
                if fallback_uid is not None:
                    self._uid_aliases[engine_uid] = fallback_uid
            uid = self._uid_aliases.get(engine_uid, engine_uid)
            if detection_backed and uid in detection_track_ids:
                continue
            if not detection_backed and uid not in self._last_seen_by_track:
                continue
            if detection_backed:
                seen_detection_indices.add(det_idx)
                detection_track_ids.add(uid)
                self._last_seen_by_track[uid] = frame_idx
                self._update_motion_state(uid, frame_idx, bbox, label)
                frame_output = [
                    box
                    for box in frame_output
                    if not (box.id == f"track-{uid}" and not box.detection_backed)
                ]
            time_since_update = (
                0 if detection_backed else max(1, frame_idx - self._last_seen_by_track[uid])
            )
            confidence = float(row[5]) if len(row) > 5 else 1.0
            if not detection_backed:
                confidence = max(0.0, confidence - time_since_update * self._confidence_decay)
            frame_output.append(
                BBoxViewModel(
                    id=f"track-{uid}",
                    source=BoxSource.TRACKING_BYTETRACK,
                    label=label,
                    bbox_xyxy=bbox,
                    color_hex=uid_to_color(uid),
                    confidence=round(confidence, 4),
                    key=f"track:{uid}",
                    detection_backed=detection_backed,
                    time_since_update=time_since_update,
                )
            )
        for detection_index, detection in enumerate(frame_boxes):
            confidence = float(detection.confidence if detection.confidence is not None else 1.0)
            birth_threshold = max(tau_low, self._min_detection_confidence)
            if confidence < birth_threshold or detection_index in seen_detection_indices:
                continue
            bbox = _as_xyxy_int(detection.bbox_xyxy)
            fallback_uid = self._best_fallback_track(
                frame_idx,
                bbox,
                detection.label,
                excluded_ids=detection_track_ids,
            )
            if fallback_uid is None:
                fallback_uid = self._next_synthetic_uid
                self._next_synthetic_uid -= 1
            # A backend may keep an unmatched coast row while this app-side
            # high-confidence birth recovers the same subject geometrically.
            frame_output = [
                box
                for box in frame_output
                if not (box.id == f"track-{fallback_uid}" and not box.detection_backed)
            ]
            self._last_seen_by_track[fallback_uid] = frame_idx
            self._update_motion_state(fallback_uid, frame_idx, bbox, detection.label)
            detection_track_ids.add(fallback_uid)
            frame_output.append(
                BBoxViewModel(
                    id=f"track-{fallback_uid}",
                    source=BoxSource.TRACKING_BYTETRACK,
                    label=detection.label,
                    bbox_xyxy=bbox,
                    color_hex=uid_to_color(fallback_uid),
                    confidence=round(confidence, 4),
                    key=f"track:{fallback_uid}",
                    detection_backed=True,
                    time_since_update=0,
                )
            )
        return frame_output

    def _best_fallback_track(
        self,
        frame_idx: int,
        bbox: tuple[int, int, int, int],
        label: str,
        *,
        excluded_ids: set[int],
    ) -> int | None:
        """Find a recently observed track by GIoU and predicted-center distance.

        Args:
            frame_idx: Current zero-based frame index.
            bbox: Current detection box.
            label: Detection class name.
            excluded_ids: Track IDs already assigned to another current row.

        Returns:
            The best plausible prior ID, or ``None`` when no safe fallback exists.

        Note:
            The predicted state is ``[xc, yc, w, h, vx, vy, vw, vh]``. The
            center-distance fallback permits reacquisition after circular motion
            even when ordinary IoU is weak, while a 30-frame age cap prevents
            long-range identity guesses.

        Example:
            track_id = strategy._best_fallback_track(12, box, "person", excluded_ids=set())
        """
        candidates: list[tuple[float, int]] = []
        for (
            track_id,
            (last_frame, previous, vx, vy, vw, vh, previous_label),
        ) in self._motion_state.items():
            age = frame_idx - last_frame
            if age <= 0 or age > 30 or track_id in excluded_ids or previous_label != label:
                continue
            x1, y1, x2, y2 = previous
            predicted_width = max(1.0, (x2 - x1) + vw * age)
            predicted_height = max(1.0, (y2 - y1) + vh * age)
            predicted_center_x = (x1 + x2) / 2.0 + vx * age
            predicted_center_y = (y1 + y2) / 2.0 + vy * age
            predicted = (
                int(round(predicted_center_x - predicted_width / 2.0)),
                int(round(predicted_center_y - predicted_height / 2.0)),
                int(round(predicted_center_x + predicted_width / 2.0)),
                int(round(predicted_center_y + predicted_height / 2.0)),
            )
            giou = _generalized_iou(predicted, bbox)
            predicted_center = ((predicted[0] + predicted[2]) / 2.0, (predicted[1] + predicted[3]) / 2.0)
            detection_center = ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)
            distance = float(np.hypot(
                predicted_center[0] - detection_center[0],
                predicted_center[1] - detection_center[1],
            ))
            diagonal = max(1.0, float(np.hypot(x2 - x1, y2 - y1)))
            normalized_distance = distance / diagonal
            if giou < -0.25 and normalized_distance > 0.75:
                continue
            candidates.append((0.65 * (1.0 - giou) / 2.0 + 0.35 * normalized_distance, track_id))
        if not candidates:
            return None
        cost, track_id = min(candidates)
        return track_id if cost <= 0.85 else None

    def _update_motion_state(
        self,
        track_id: int,
        frame_idx: int,
        bbox: tuple[int, int, int, int],
        label: str,
    ) -> None:
        """Update constant-velocity center and size estimates for a matched track.

        Args:
            track_id: Canonical track identifier.
            frame_idx: Current zero-based frame index.
            bbox: Current detection-backed box.
            label: Detection class name.

        Note:
            The state is ``[xc, yc, w, h, vx, vy, vw, vh]``. Measured center
            displacement and size changes are blended with prior velocity to
            dampen detector jitter while retaining fast direction changes.

        Example:
            strategy._update_motion_state(4, 10, box, "person")
        """
        previous_state = self._motion_state.get(track_id)
        vx = vy = vw = vh = 0.0
        if previous_state is not None:
            (
                previous_frame,
                previous,
                previous_vx,
                previous_vy,
                previous_vw,
                previous_vh,
                _,
            ) = previous_state
            elapsed = frame_idx - previous_frame
            if elapsed > 0:
                measured_vx = (
                    (bbox[0] + bbox[2] - previous[0] - previous[2]) / 2.0 / elapsed
                )
                measured_vy = (
                    (bbox[1] + bbox[3] - previous[1] - previous[3]) / 2.0 / elapsed
                )
                measured_vw = ((bbox[2] - bbox[0]) - (previous[2] - previous[0])) / elapsed
                measured_vh = ((bbox[3] - bbox[1]) - (previous[3] - previous[1])) / elapsed
                vx = 0.5 * previous_vx + 0.5 * measured_vx
                vy = 0.5 * previous_vy + 0.5 * measured_vy
                vw = 0.5 * previous_vw + 0.5 * measured_vw
                vh = 0.5 * previous_vh + 0.5 * measured_vh
        self._motion_state[track_id] = (frame_idx, bbox, vx, vy, vw, vh, label)

    def track(
        self,
        source_data: ListOfBoxesByFrameIndexAsDict,
        total_frames: int = 0,
    ) -> ListOfBoxesByFrameIndexAsDict:
        """Run the incremental strategy over a complete detection frame map.

        Args:
            source_data: Per-frame detections to associate.
            total_frames: Number of frames to process.

        Returns:
            Tracking boxes keyed by frame index with observation-age metadata.
        """
        if not source_data:
            return {}
        tracked = {
            frame_idx: self.update_frame(frame_idx, source_data.get(frame_idx, []))
            for frame_idx in range(total_frames)
        }
        logger.debug("ByteTrack strategy finished. Output frames: {}", len(tracked))
        return tracked
