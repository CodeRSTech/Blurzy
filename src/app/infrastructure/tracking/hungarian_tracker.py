r"""
HungarianIoUTracker — pure NumPy/SciPy multi-object tracker.

Architectural contract
----------------------
- ZERO Qt dependencies.
- ZERO UI / views imports.
- Accepts and returns only plain Python / NumPy data.
- The TrackingWorker (infrastructure layer) is responsible for unpacking
  ReviewFrameItemViewModel dicts, feeding this engine, and repacking results.

Algorithm
---------
1. For each new frame, compute IoU between all active tracks and all detections.
2. Build a cost matrix  (cost = 1.0 - IoU).
3. Solve the linear assignment problem with scipy.optimize.linear_sum_assignment.
4. Accept matches whose IoU >= iou_threshold.
5. Unmatched detections → new tracks.
6. Unmatched tracks → coast internally (move by last velocity, decay confidence).
7. Tracks whose confidence drops below min_confidence are pruned; unobserved states are not emitted.

For axis-aligned boxes, the overlap and assignment cost are

$$
\operatorname{IoU}(A,B)=\frac{|A\cap B|}{|A\cup B|},
\qquad C_{ij}=1-\operatorname{IoU}(T_i,D_j).
$$

The Hungarian solver minimizes total assignment cost; a candidate match is
accepted only when its IoU meets `iou_threshold`.

See Also:
    - [`HungarianStrategy`][app.infrastructure.tracking.tracking_strategy.HungarianStrategy] — adapts the tracker to frame-based strategy dispatch
    - [`TrackingWorker`][app.infrastructure.tracking.track_worker.TrackingWorker] — sends per-frame detections to tracker strategies

Layer: Infrastructure tracking.
Context: A Qt-independent tracker consumes plain detections and returns
per-frame track states to the tracking worker.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from dataclasses import dataclass, field
from typing import final

import numpy as np
from scipy.optimize import linear_sum_assignment

from app.shared.logging_cfg import get_logger
if TYPE_CHECKING:
    from app.domain.base.dtypes import BBoxXYXYTuple


logger = get_logger("Infrastructure->HungarianTracker")

# [NOTE]
#  Flat is better than nested. (Zen of Python)
#  ----
#  The Mistake:
#   Multi-object tracking algorithms naturally trend toward deeply nested loops:
#     for frame in frames:
#     for track in tracks:
#     if track.is_active:
#     if iou > threshold: ...
#   This violates the Zen of Python and destroys readability.

# TODO:
#  Vectorize it or use Early Returns.
#  Since we are using SciPy's linear_sum_assignment, we have to
#  ensure your cost matrix generation (IoU calculation) is done entirely in
#  NumPy matrix operations rather than nested for loops.

# ---------------------------------------------------------------------------
# Public data contract
# ---------------------------------------------------------------------------

@dataclass
class TrackInput:
    """
    One detection handed to the tracker for a single frame.

    Layer: Infrastructure.
    Context: Implements concrete processing or I/O behind application-facing contracts.
    """
    bbox_xyxy: BBoxXYXYTuple  # (x1, y1, x2, y2)
    confidence: float
    label: str


@dataclass
class TrackState:
    """
    The live view_state of one confirmed track, returned per frame.

    Layer: Infrastructure.
    Context: Implements concrete processing or I/O behind application-facing contracts.
    """
    uid: int
    bbox_xyxy: BBoxXYXYTuple
    confidence: float
    label: str
    # velocity in (x, y) pixels — centroid-based, updated on each match
    velocity: tuple[float, float] = field(default=(0.0, 0.0))
    observed: bool = True
    time_since_update: int = 0


# ---------------------------------------------------------------------------
# Internal track record (not exposed to callers)
# ---------------------------------------------------------------------------

@dataclass
class _Track:
    uid: int
    bbox_xyxy: BBoxXYXYTuple
    confidence: float
    label: str
    velocity: tuple[float, float] = field(default=(0.0, 0.0))
    observed: bool = True
    time_since_update: int = 0

    def centroid(self) -> tuple[float, float]:
        """
        Return the center point of the track's `xyxy` box.

        Returns:
            `(x, y)` centroid coordinates in pixels.
        """
        x1, y1, x2, y2 = self.bbox_xyxy
        return (x1 + x2) / 2.0, (y1 + y2) / 2.0

    def coast(self, confidence_decay: float) -> None:
        """
        Advance a missed track and record its coast age.

        Args:
            confidence_decay: Confidence reduction per unmatched frame.

        Note:
            The bounding box moves by the last observed velocity and the age
            increments once for each unmatched frame.

        Example:
            track.coast(confidence_decay=0.05)
        """
        dx, dy = self.velocity
        x1, y1, x2, y2 = self.bbox_xyxy
        self.bbox_xyxy = (
            int(round(x1 + dx)),
            int(round(y1 + dy)),
            int(round(x2 + dx)),
            int(round(y2 + dy)),
        )
        self.confidence = max(0.0, self.confidence - confidence_decay)
        self.time_since_update += 1

    def to_state(self) -> TrackState:
        """
        Copy the current record into its public track-state value.

        Returns:
            Snapshot including velocity, observation status, and track age.
        """
        return TrackState(
            uid=self.uid,
            bbox_xyxy=self.bbox_xyxy,
            confidence=self.confidence,
            label=self.label,
            velocity=self.velocity,
            observed=self.observed,
            time_since_update=self.time_since_update,
        )


# ---------------------------------------------------------------------------
# IoU utility
# ---------------------------------------------------------------------------

def _iou_matrix(
        tracks: list[_Track],
        detections: list[TrackInput],
) -> np.ndarray:
    """
    Return an (n_tracks × n_detections) IoU matrix.
"""
    n_t = len(tracks)
    n_d = len(detections)
    mat = np.zeros((n_t, n_d), dtype=np.float32)

    for ti, track in enumerate(tracks):
        tx1, ty1, tx2, ty2 = track.bbox_xyxy
        for di, det in enumerate(detections):
            dx1, dy1, dx2, dy2 = det.bbox_xyxy

            inter_x1 = max(tx1, dx1)
            inter_y1 = max(ty1, dy1)
            inter_x2 = min(tx2, dx2)
            inter_y2 = min(ty2, dy2)

            inter_w = max(0, inter_x2 - inter_x1)
            inter_h = max(0, inter_y2 - inter_y1)
            inter_area = inter_w * inter_h

            area_t = max(0, tx2 - tx1) * max(0, ty2 - ty1)
            area_d = max(0, dx2 - dx1) * max(0, dy2 - dy1)
            union_area = area_t + area_d - inter_area

            mat[ti, di] = inter_area / union_area if union_area > 0 else 0.0

    return mat


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------

@final
class HungarianIoUTracker:
    """
    Associate frame detections with active tracks by global IoU assignment.

    Layer: Infrastructure tracking.
    Context: Owns the live track set used by a tracking strategy adapter.

    Args:
        iou_threshold: Minimum IoU required to accept a detection-track match.
        confidence_decay: Confidence decrease applied to a track per missed frame.
        min_confidence: Minimum confidence at which an unmatched track remains active.
    """
    def __init__(
            self,
            iou_threshold: float = 0.3,
            confidence_decay: float = 0.05,
            min_confidence: float = 0.1,
    ) -> None:
        self._iou_threshold = iou_threshold
        self._confidence_decay = confidence_decay
        self._min_confidence = min_confidence

        self._tracks: list[_Track] = []
        self._next_uid: int = 1

        logger.debug("HungarianIoUTracker initialized with iou_threshold={}, min_confidence={}", iou_threshold,
                     min_confidence)

    def reset(self) -> None:
        """
        Clear all live tracks and reset the UID counter.
"""
        logger.debug("HungarianIoUTracker internal view_state reset")
        self._tracks = []
        self._next_uid = 1

    def update(self, detections: list[TrackInput]) -> list[TrackState]:
        """
        Associate one frame of detections and advance unmatched tracks.

        Args:
            detections: Detection boxes for the current frame.

        Returns:
            Current active track states, including coast age and observation flags.

        Raises:
            ValueError: If the assignment solver rejects the cost matrix.

        Note:
            Coast states remain active until their confidence falls below the
            configured floor, allowing later detections to reconnect.

        Example:
            states = tracker.update([TrackInput((0, 0, 10, 10), 0.9, "person")])
        """
        if not self._tracks and not detections:
            return []

        logger.trace("Engine Update Tick | Detections: {} | Live Tracks: {}", len(detections), len(self._tracks))

        coasted_tracks: list[_Track] = []
        for t in self._tracks:
            import copy as _copy
            ct = _copy.copy(t)
            ct.coast(self._confidence_decay)
            coasted_tracks.append(ct)

        matched_track_ids: set[int] = set()
        matched_det_ids: set[int] = set()
        matches: list[tuple[int, int]] = []

        if coasted_tracks and detections:
            iou_mat = _iou_matrix(coasted_tracks, detections)
            cost_mat = 1.0 - iou_mat

            row_indices, col_indices = linear_sum_assignment(cost_mat)  # allow untyped libraries in toml

            for row, col in zip(row_indices, col_indices):
                iou_val = iou_mat[row, col]
                if iou_val >= self._iou_threshold:
                    matches.append((row, col))
                    matched_track_ids.add(row)
                    matched_det_ids.add(col)

        logger.trace("  -> Step 2: Found {} IoU matches above threshold", len(matches))

        for track_idx, det_idx in matches:
            old_track = self._tracks[track_idx]
            det = detections[det_idx]

            old_cx, old_cy = old_track.centroid()
            x1, y1, x2, y2 = det.bbox_xyxy
            new_cx = (x1 + x2) / 2.0
            new_cy = (y1 + y2) / 2.0

            old_track.bbox_xyxy = det.bbox_xyxy
            old_track.confidence = 1.0
            old_track.label = det.label
            old_track.velocity = (new_cx - old_cx, new_cy - old_cy)
            old_track.observed = True
            old_track.time_since_update = 0

        coasted_count = 0
        for idx, track in enumerate(self._tracks):
            if idx not in matched_track_ids:
                track.coast(self._confidence_decay)
                track.observed = False
                coasted_count += 1

        if coasted_count > 0:
            logger.trace("  -> Step 4: Coasted {} unmatched tracks", coasted_count)

        spawned_count = 0
        for det_idx, det in enumerate(detections):
            if det_idx not in matched_det_ids:
                self._tracks.append(
                    _Track(
                        uid=self._next_uid,
                        bbox_xyxy=det.bbox_xyxy,
                        confidence=det.confidence,
                        label=det.label,
                    )
                )
                self._next_uid += 1
                spawned_count += 1

        if spawned_count > 0:
            logger.trace("  -> Step 5: Spawned {} new tracks", spawned_count)

        pre_prune_len = len(self._tracks)
        self._tracks = [
            t for t in self._tracks if t.confidence >= self._min_confidence
        ]
        if len(self._tracks) < pre_prune_len:
            logger.trace("  -> Step 6: Pruned {} dead tracks", pre_prune_len - len(self._tracks))

        return [t.to_state() for t in self._tracks]
