from __future__ import annotations

import copy

from app.domain.base.dtypes import ListOfBoxesByFrameIndexAsDict
from app.domain.detection import BoxSource
from app.domain.views import BBoxViewModel
from app.infrastructure.tracking.hungarian_tracker import HungarianIoUTracker, TrackInput, TrackState
from app.shared.logging_cfg import get_logger

logger = get_logger("Infrastructure->Tracking->HungarianStrategy")

_TRACK_PALETTE: list[str] = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#42d4f4",
    "#f032e6", "#bfef45", "#fabed4", "#469990", "#dcbeff",
    "#9a6324", "#fffac8", "#800000", "#aaffc3", "#000075",
    "#a9a9a9", "#ffffff", "#ffe119", "#911eb4", "#ffd8b1",
]

def uid_to_color(uid: int) -> str:
    """Map track UID to color (wraps around palette for >20 tracks)."""
    return _TRACK_PALETTE[(uid - 1) % len(_TRACK_PALETTE)]


class HungarianStrategy:
    """Tracking strategy using Hungarian algorithm with IoU matching (see ``HungarianIoUTracker``)."""

    def __init__(
            self,
            iou_threshold: float = 0.3,
            confidence_decay: float = 0.05,
            min_confidence: float = 0.1,
    ) -> None:
        """Initialize ``HungarianIoUTracker`` with matching and decay parameters."""
        self._engine = HungarianIoUTracker(
            iou_threshold=iou_threshold,
            confidence_decay=confidence_decay,
            min_confidence=min_confidence,
        )

    def track(
            self,
            source_data: ListOfBoxesByFrameIndexAsDict,
            total_frames: int,
    ) -> ListOfBoxesByFrameIndexAsDict:
        """Run Hungarian IoU tracker on all frames, return tracked boxes with unique IDs and colors."""
        logger.info("Hungarian Tracker engine starting for {} populated frames", len(source_data))
        self._engine.reset()
        tracked: ListOfBoxesByFrameIndexAsDict = {}

        if not source_data:
            return {}

        # Safely find the last known detection
        last_seen_detection_index = max(source_data.keys())
        frame_idx = 0

        while frame_idx < total_frames:
            # Use .get() to pull the frame. If it doesn't exist, it defaults to []
            frame_boxes = source_data.get(frame_idx, [])

            detections = [
                TrackInput(
                    bbox_xyxy=item.bbox_xyxy,
                    confidence=item.confidence if item.confidence is not None else 1.0,
                    label=item.label,
                )
                for item in frame_boxes
            ]

            active: list[TrackState] = self._engine.update(detections)

            is_active = len(active) > 0

            # Stop early to save CPU if we've passed the last detection AND all tracks have fully died/decayed
            if frame_idx > last_seen_detection_index and not is_active:
                break

            tracked[frame_idx] = [
                BBoxViewModel(
                    id=f"track-{t.uid}",
                    source= BoxSource.TRACKING_HUNGARIAN,
                    label=t.label,
                    bbox_xyxy=t.bbox_xyxy,
                    color_hex=uid_to_color(t.uid),
                    confidence=round(t.confidence, 4),
                    key=f"track:{t.uid}",
                )
                for t in active
            ]

            frame_idx += 1

        logger.debug("Hungarian Tracker engine finished processing all sparse frames")
        return tracked


class DummyTracker:
    """No-op tracker — passes through detections as-is, marks with magenta (#ff00ff)."""

    @staticmethod
    def track(source_data: ListOfBoxesByFrameIndexAsDict, total_frames: int = 0) -> ListOfBoxesByFrameIndexAsDict:
        """Return detections unchanged, just update source/color/key labels."""
        tracked: ListOfBoxesByFrameIndexAsDict = {}
        for frame_idx, boxes in source_data.items():
            tracked[frame_idx] = []
            for item in boxes:
                new_item = copy.deepcopy(item)
                new_item.source = BoxSource.TRACKING_DUMMY
                new_item.color_hex = "#ff00ff"
                new_item.key = f"track:{new_item.id}"
                tracked[frame_idx].append(new_item)
        return tracked
