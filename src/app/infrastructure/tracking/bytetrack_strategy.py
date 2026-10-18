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
        confidence_decay: float = 0.05,
    ) -> None:
        """Initialize ByteTrack and app-side labels and coast confidence.

        Args:
            min_iou: IoU similarity used to configure tracker association.
            min_confidence: Minimum confidence for accepting tracker output.
            confidence_decay: Confidence reduction per coasted frame.

        Returns:
            None.

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
        self._label_to_id: dict[str, int] = {}
        self._id_to_label: dict[int, str] = {}

        tracker_args = SimpleNamespace(
            track_high_thresh=max(min_confidence, 0.5),
            track_low_thresh=min_confidence,
            new_track_thresh=max(min_confidence, 0.4),
            track_buffer=30,
            match_thresh=min(max(min_iou, 0.1), 0.95),
            fuse_score=True,
        )
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
        det_rows = [
            [
                *item.bbox_xyxy,
                float(item.confidence if item.confidence is not None else 1.0),
                float(self._class_id_for_label(item.label)),
            ]
            for item in frame_boxes
        ]
        det_arr = np.asarray(det_rows, dtype=np.float32) if det_rows else np.empty((0, 6), dtype=np.float32)
        boxes = self._boxes_cls(det_arr, (1, 1))
        active_tracks = self._engine.update(boxes)
        frame_output: list[BBoxViewModel] = []
        for row in active_tracks if getattr(active_tracks, "size", 0) else []:
            det_idx = int(row[7]) if len(row) > 7 else -1
            uid = int(row[4])
            detection_backed = 0 <= det_idx < len(frame_boxes)
            if not detection_backed and uid not in self._last_seen_by_track:
                continue
            if detection_backed:
                self._last_seen_by_track[uid] = frame_idx
            time_since_update = (
                0 if detection_backed else max(1, frame_idx - self._last_seen_by_track[uid])
            )
            bbox = _as_xyxy_int(row[:4])
            cls_id = int(row[6]) if len(row) > 6 else -1
            label = self._id_to_label.get(cls_id, f"class-{cls_id}")
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
        return frame_output

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
