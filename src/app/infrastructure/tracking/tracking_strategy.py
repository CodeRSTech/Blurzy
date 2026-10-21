"""Module for tracking strategy; implements concrete processing and I/O behind application-facing contracts.

Layer: Infrastructure.
Context: Implements concrete processing and i/o behind application-facing contracts at this architectural boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import copy
import numpy as np

from app.domain.detection import BoxSource
from app.domain.views import BBoxViewModel
from app.infrastructure.tracking.hungarian_tracker import HungarianIoUTracker, TrackInput
from app.shared.logging_cfg import get_logger
if TYPE_CHECKING:
    from typing import Sequence
    from app.domain.base.dtypes import ListOfBoxesByFrameIndexAsDict
    from app.infrastructure.dtypes import RGBFrame
    from app.infrastructure.tracking.hungarian_tracker import TrackState


logger = get_logger("Infrastructure->Tracking->HungarianStrategy")

_TRACK_PALETTE: list[str] = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#42d4f4",
    "#f032e6", "#bfef45", "#fabed4", "#469990", "#dcbeff",
    "#9a6324", "#fffac8", "#800000", "#aaffc3", "#000075",
    "#a9a9a9", "#ffffff", "#ffe119", "#911eb4", "#ffd8b1",
]

def uid_to_color(uid: int) -> str:
    """Map track UID to color (wraps around palette for >20 tracks).

    Args:
        uid: Positive track identifier used to select a palette entry.

    Returns:
        Hex color selected cyclically from the tracking palette.
    """
    return _TRACK_PALETTE[(uid - 1) % len(_TRACK_PALETTE)]


class HungarianStrategy:
    """Tracking strategy using Hungarian algorithm with IoU matching (see `HungarianIoUTracker`).

Layer: Infrastructure.
Context: Implements concrete processing or I/O behind application-facing contracts.
"""

    uses_appearance = False

    def __init__(
            self,
            iou_threshold: float = 0.3,
            confidence_decay: float = 0.05,
            min_confidence: float = 0.1,
    ) -> None:
        """Initialize the tracker with match and coast thresholds.

        Args:
            iou_threshold: Minimum IoU accepted for a detection-track match.
            confidence_decay: Per-frame confidence penalty while coasting.
            min_confidence: Confidence floor used to prune internal tracks.

        Note:
            Coasting states are retained in output with `detection_backed=False`.

        Example:
            strategy = HungarianStrategy(iou_threshold=0.3, confidence_decay=0.05)
        """
        self._engine = HungarianIoUTracker(
            iou_threshold=iou_threshold,
            confidence_decay=confidence_decay,
            min_confidence=min_confidence,
        )

    def update_frame(
        self,
        frame_idx: int,
        frame_boxes: list[BBoxViewModel],
        frame: RGBFrame | None = None,
        embeddings: Sequence[np.ndarray | None] | None = None,
    ) -> list[BBoxViewModel]:
        """Update state with one frame and return active detection/coast boxes.

        Args:
            frame_idx: Zero-based frame index.
            frame_boxes: Detection boxes for the current frame.
            frame: Optional RGB frame, unused by this motion-only strategy.
            embeddings: Optional box-aligned appearance features, unused here.

        Returns:
            Active tracker boxes for the current frame.
        """
        if frame_idx == 0:
            self._engine.reset()
        detections = [
            TrackInput(
                bbox_xyxy=item.bbox_xyxy,
                confidence=item.confidence if item.confidence is not None else 1.0,
                label=item.label,
            )
            for item in frame_boxes
        ]
        active: list[TrackState] = self._engine.update(detections)
        return [
            BBoxViewModel(
                id=f"track-{track.uid}",
                source=BoxSource.TRACKING_HUNGARIAN,
                label=track.label,
                bbox_xyxy=track.bbox_xyxy,
                color_hex=uid_to_color(track.uid),
                confidence=round(track.confidence, 4),
                key=f"track:{track.uid}",
                detection_backed=track.observed,
                time_since_update=track.time_since_update,
            )
            for track in active
        ]

    def track(
        self,
        source_data: ListOfBoxesByFrameIndexAsDict,
        total_frames: int,
    ) -> ListOfBoxesByFrameIndexAsDict:
        """Run the incremental strategy over a complete frame map.

        Args:
            source_data: Per-frame detection input.
            total_frames: Number of frames to process.

        Returns:
            Boxes keyed by frame, with detection-backed and coast-age metadata.
        """
        logger.info("Hungarian Tracker engine starting for {} populated frames", len(source_data))
        self._engine.reset()
        if not source_data:
            return {}
        tracked = {
            frame_idx: self.update_frame(frame_idx, source_data.get(frame_idx, []))
            for frame_idx in range(total_frames)
        }
        logger.debug("Hungarian Tracker engine finished processing all sparse frames")
        return tracked


class DummyTracker:
    """No-op tracker — passes through detections as-is, marks with magenta (#ff00ff).

Layer: Infrastructure.
Context: Implements concrete processing or I/O behind application-facing contracts.
"""

    uses_appearance = False

    @staticmethod
    def update_frame(
        frame_idx: int,
        frame_boxes: list[BBoxViewModel],
        frame: RGBFrame | None = None,
        embeddings: Sequence[np.ndarray | None] | None = None,
    ) -> list[BBoxViewModel]:
        """Copy and retag detections for one frame.

        Args:
            frame_idx: Zero-based frame index.
            frame_boxes: Detection boxes to copy.
            frame: Optional RGB frame, unused by this strategy.
            embeddings: Optional appearance features, unused by this strategy.

        Returns:
            Copied boxes marked as dummy tracking output.
        """
        output: list[BBoxViewModel] = []
        for item in frame_boxes:
            new_item = copy.deepcopy(item)
            new_item.source = BoxSource.TRACKING_DUMMY
            new_item.color_hex = "#ff00ff"
            new_item.key = f"track:{new_item.id}"
            output.append(new_item)
        return output

    @staticmethod
    def track(source_data: ListOfBoxesByFrameIndexAsDict, total_frames: int = 0) -> ListOfBoxesByFrameIndexAsDict:
        """Return detections unchanged, just update source/color/key labels.

        Args:
            source_data: Detection boxes grouped by frame index.
            total_frames: Retained for tracker API compatibility; this implementation does not use it.

        Returns:
            New frame mapping containing deep-copied boxes retagged as dummy tracks.
        """
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
