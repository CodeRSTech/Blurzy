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
    from typing import Any
    from app.domain.base.dtypes import ListOfBoxesByFrameIndexAsDict


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

    def __init__(self, min_iou: float = 0.3, min_confidence: float = 0.1) -> None:
        try:
            from ultralytics.trackers.byte_tracker import BYTETracker  # pyright: ignore[reportMissingImports]
            from ultralytics.engine.results import Boxes  # pyright: ignore[reportMissingImports]
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "ByteTrack strategy requires 'ultralytics'. Install dependencies to use strategy='bytetrack'."
            ) from exc

        self._boxes_cls = Boxes
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

    def track(
            self,
            source_data: ListOfBoxesByFrameIndexAsDict,
            total_frames: int = 0,
    ) -> ListOfBoxesByFrameIndexAsDict:
        tracked: ListOfBoxesByFrameIndexAsDict = {}
        if not source_data:
            return tracked

        last_seen_detection_index = max(source_data.keys())
        frame_idx = 0
        while frame_idx < total_frames:
            frame_boxes = source_data.get(frame_idx, [])
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
            # Output row shape: [x1, y1, x2, y2, track_id, score, cls, det_idx]
            for row in active_tracks if getattr(active_tracks, "size", 0) else []:
                uid = int(row[4])
                bbox = _as_xyxy_int(row[:4])
                cls_id = int(row[6]) if len(row) > 6 else -1
                label = self._id_to_label.get(cls_id, f"class-{cls_id}")
                confidence = float(row[5]) if len(row) > 5 else 1.0
                frame_output.append(
                    BBoxViewModel(
                        id=f"track-{uid}",
                        source=BoxSource.TRACKING_BYTETRACK,
                        label=label,
                        bbox_xyxy=bbox,
                        color_hex=uid_to_color(uid),
                        confidence=round(confidence, 4),
                        key=f"track:{uid}",
                    )
                )

            has_active = len(frame_output) > 0
            if frame_idx > last_seen_detection_index and not has_active:
                break

            tracked[frame_idx] = frame_output
            frame_idx += 1

        logger.debug("ByteTrack strategy finished. Output frames: {}", len(tracked))
        return tracked
