"""Offline tracklet stitching and bounded Gaussian interpolation."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import TYPE_CHECKING

import numpy as np
from scipy.optimize import linear_sum_assignment

from app.domain.views import BBoxViewModel
from app.shared.logging_cfg import get_logger

if TYPE_CHECKING:
    from app.domain.base.dtypes import ListOfBoxesByFrameIndexAsDict

logger = get_logger("Infrastructure->Tracking->PostProcessor")

_INVALID_COST = 1_000_000.0
_MAX_LINK_COST = 0.35
# Reject near-tied assignments when the second choice is within five cost points.
_AMBIGUITY_MARGIN = 0.05


@dataclass(slots=True)
class _Tracklet:
    key: tuple[str, int]
    track_id: str
    boxes: dict[int, BBoxViewModel]

    @property
    def frames(self) -> list[int]:
        return sorted(self.boxes)

    @property
    def start_frame(self) -> int:
        return min(self.boxes)

    @property
    def end_frame(self) -> int:
        return max(self.boxes)

    def velocity(self, *, at_end: bool, window: int = 5) -> np.ndarray:
        frames = self.frames
        selected = frames[-window:] if at_end else frames[:window]
        if len(selected) < 2:
            return np.zeros(4, dtype=np.float64)
        first = np.asarray(self.boxes[selected[0]].bbox_xyxy, dtype=np.float64)
        last = np.asarray(self.boxes[selected[-1]].bbox_xyxy, dtype=np.float64)
        return (last - first) / (selected[-1] - selected[0])


class TrackingPostProcessor:
    """Optionally stitch tracklets and generate confidence-bounded coast estimates.

    Args:
        max_gap: Maximum number of missed frames bridged by offline stitching.
        gsi_smoothness: Gaussian kernel lengthscale used to blend gap predictions.
        confidence_decay: Per-missed-frame confidence penalty.
        min_confidence: Minimum confidence retained in tracking output.
        offline_stitching_enabled: Whether to link tracklets and use GSI.
        max_unbridged_coast: Maximum coast frames for unbridged offline tails.

    Raises:
        ValueError: If any numeric setting is outside its supported range.

    Note:
        With offline stitching enabled, coasted input boxes are discarded in favor
        of detection-backed observations, stitched GSI gaps, and short 2x-decay
        tails. With stitching disabled, missing frames use causal 1x-decay estimates.

    Example:
        processor = TrackingPostProcessor(max_gap=25, gsi_smoothness=10.0)
        results = processor.process(track_data, total_frames=300)
    """

    def __init__(
        self,
        max_gap: int = 25,
        gsi_smoothness: float = 10.0,
        confidence_decay: float = 0.05,
        min_confidence: float = 0.1,
        offline_stitching_enabled: bool = True,
        max_unbridged_coast: int = 6,
    ) -> None:
        if not 1 <= max_gap <= 60:
            raise ValueError("max_gap must be between 1 and 60 frames.")
        if not 1.0 <= gsi_smoothness <= 30.0:
            raise ValueError("gsi_smoothness must be between 1.0 and 30.0.")
        if confidence_decay < 0.0:
            raise ValueError("confidence_decay must be non-negative.")
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be between 0 and 1.")
        if max_unbridged_coast < 0:
            raise ValueError("max_unbridged_coast must be non-negative.")
        self._max_gap = max_gap
        self._gsi_smoothness = gsi_smoothness
        self._confidence_decay = confidence_decay
        self._min_confidence = min_confidence
        self._offline_stitching_enabled = offline_stitching_enabled
        self._max_unbridged_coast = max_unbridged_coast

    def process(
        self,
        tracked_data: ListOfBoxesByFrameIndexAsDict,
        total_frames: int | None = None,
    ) -> ListOfBoxesByFrameIndexAsDict:
        """Post-process observations into stitched or causal tracking output.

        Args:
            tracked_data: Tracker output keyed by zero-based frame index.
            total_frames: Optional video frame count used to bound final coast tails.

        Returns:
            A sorted frame-to-box mapping containing observations and accepted coasts.

        Raises:
            ValueError: If ``total_frames`` is negative.

        Note:
            Legacy boxes without coast metadata are treated as detection-backed.

        Example:
            output = processor.process(raw_tracks, total_frames=120)
        """
        if total_frames is not None and total_frames < 0:
            raise ValueError("total_frames must be non-negative.")

        observations = {
            frame_index: [
                box for box in boxes
                if box.detection_backed and box.time_since_update == 0
            ]
            for frame_index, boxes in tracked_data.items()
        }
        tracklets, segment_by_observation = self._extract_tracklets(observations)
        links = self._assign_links(tracklets) if self._offline_stitching_enabled else []

        predecessors = {target: source for source, target in links}

        def root_key(key: tuple[str, int]) -> tuple[str, int]:
            while key in predecessors:
                key = predecessors[key]
            return key

        final_frame_count = total_frames
        if final_frame_count is None:
            final_frame_count = max(tracked_data, default=-1) + 1
        output: ListOfBoxesByFrameIndexAsDict = {
            frame_index: [] for frame_index in range(final_frame_count)
        }
        for frame_index in tracked_data:
            output.setdefault(frame_index, [])
        canonical_boxes = {
            key: tracklet.boxes[tracklet.start_frame]
            for key, tracklet in tracklets.items()
        }
        for frame_index, boxes in observations.items():
            for box in boxes:
                key = segment_by_observation[(frame_index, box.id)]
                template = canonical_boxes[root_key(key)]
                if template.id == box.id:
                    output[frame_index].append(box)
                    continue
                clone = box.clone()
                clone.id = template.id
                clone.key = template.key
                clone.color_hex = template.color_hex
                output[frame_index].append(clone)

        provided_coasts: set[tuple[int, str]] = set()
        if not self._offline_stitching_enabled:
            for frame_index, boxes in tracked_data.items():
                for box in boxes:
                    if box.detection_backed and box.time_since_update == 0:
                        continue
                    confidence = box.confidence if box.confidence is not None else 1.0
                    if confidence < self._min_confidence:
                        continue
                    coast = box.clone()
                    output.setdefault(frame_index, []).append(coast)
                    provided_coasts.add((frame_index, box.id))

        interpolated_count = 0
        for source_key, target_key in links:
            source = tracklets[source_key]
            target = tracklets[target_key]
            template = canonical_boxes[root_key(source_key)]
            interpolated_count += self._fill_gap(
                output, source, target, template, self._gsi_smoothness
            )

        self._fill_unbridged_coasts(
            output,
            tracklets,
            links,
            provided_coasts,
            {key: canonical_boxes[root_key(key)] for key in tracklets},
            total_frames=final_frame_count,
        )

        logger.debug(
            "Offline tracking post-processing linked {} tracklet pair(s) across {} frame(s)",
            len(links),
            interpolated_count,
        )
        return dict(sorted(output.items()))

    def _fill_unbridged_coasts(
        self,
        output: ListOfBoxesByFrameIndexAsDict,
        tracklets: dict[tuple[str, int], _Tracklet],
        links: list[tuple[tuple[str, int], tuple[str, int]]],
        provided_coasts: set[tuple[int, str]],
        canonical_boxes: dict[tuple[str, int], BBoxViewModel],
        *,
        total_frames: int,
    ) -> None:
        """Add bounded forward predictions wherever no accepted GSI bridge exists.

        Args:
            output: Mutable output frame map receiving coast estimates.
            tracklets: Detection-backed track segments.
            links: Accepted source-to-target offline links.
            provided_coasts: Tracker-provided causal coast frame/ID pairs.
            canonical_boxes: Root identity template for each tracklet.
            total_frames: Exclusive end of the video frame range.

        Returns:
            None.

        Raises:
            None.

        Note:
            Same-class observations at a frame stop a coast instead of adding an
            ambiguous ghost beside a different detected subject.

        Example:
            processor._fill_unbridged_coasts(output, tracklets, links, templates, total_frames=60)
        """
        linked_sources = {source for source, _ in links}
        bridged_frames: set[tuple[int, str]] = set()
        for source_key, target_key in links:
            source = tracklets[source_key]
            target = tracklets[target_key]
            bridged_frames.update(
                (frame_index, source.track_id)
                for frame_index in range(source.end_frame + 1, target.start_frame)
            )

        tracklets_by_id: dict[str, list[_Tracklet]] = {}
        for tracklet in tracklets.values():
            tracklets_by_id.setdefault(tracklet.track_id, []).append(tracklet)
        for fragments in tracklets_by_id.values():
            fragments.sort(key=lambda item: item.start_frame)

        for tracklet in tracklets.values():
            fragments = tracklets_by_id[tracklet.track_id]
            next_fragment = next(
                (item for item in fragments if item.start_frame > tracklet.end_frame),
                None,
            )
            gap_limit = next_fragment.start_frame if next_fragment else total_frames
            if (
                self._offline_stitching_enabled
                and tracklet.key in linked_sources
            ):
                continue

            max_age = (
                self._max_unbridged_coast
                if self._offline_stitching_enabled
                else total_frames - tracklet.end_frame - 1
            )
            # Six frames are a short safety bridge (~0.24 s at 25 FPS), not a
            # substitute for a missing detection sequence or a source that left frame.
            for age in range(1, max_age + 1):
                frame_index = tracklet.end_frame + age
                if frame_index >= min(total_frames, gap_limit):
                    break
                if (frame_index, tracklet.track_id) in provided_coasts:
                    continue
                if any(
                    box.detection_backed and box.label == tracklet.boxes[tracklet.end_frame].label
                    for box in output.get(frame_index, [])
                ):
                    break
                if (frame_index, tracklet.track_id) in bridged_frames:
                    continue
                coast = self._coast_box(tracklet, age, canonical_boxes[tracklet.key])
                if coast is None:
                    break
                output.setdefault(frame_index, []).append(coast)

    @staticmethod
    def _extract_tracklets(
        tracked_data: ListOfBoxesByFrameIndexAsDict,
    ) -> tuple[dict[tuple[str, int], _Tracklet], dict[tuple[int, str], tuple[str, int]]]:
        grouped: dict[str, dict[int, BBoxViewModel]] = {}
        for frame_index in sorted(tracked_data):
            for box in tracked_data[frame_index]:
                grouped.setdefault(box.id, {}).setdefault(frame_index, box)

        tracklets: dict[tuple[str, int], _Tracklet] = {}
        segment_by_observation: dict[tuple[int, str], tuple[str, int]] = {}
        for track_id, observations in grouped.items():
            frames = sorted(observations)
            segments: list[list[int]] = []
            for frame_index in frames:
                if not segments or frame_index - segments[-1][-1] > 1:
                    segments.append([])
                segments[-1].append(frame_index)

            for segment_frames in segments:
                key = (track_id, segment_frames[0])
                tracklets[key] = _Tracklet(
                    key=key,
                    track_id=track_id,
                    boxes={frame: observations[frame] for frame in segment_frames},
                )
                for frame in segment_frames:
                    segment_by_observation[(frame, track_id)] = key
        return tracklets, segment_by_observation

    def _assign_links(
        self, tracklets: dict[tuple[str, int], _Tracklet]
    ) -> list[tuple[tuple[str, int], tuple[str, int]]]:
        """Assign non-ambiguous temporal links between tracklets.

        Args:
            tracklets: Candidate tracklets keyed by original ID and start frame.

        Returns:
            One-to-one source and target tracklet key pairs.

        Raises:
            ValueError: If SciPy cannot solve an invalid assignment matrix.

        Note:
            Class agreement, maximum missed-frame count, projected geometry, and
            alternative-cost margin all constrain accepted links.

        Example:
            links = processor._assign_links(tracklets)
        """
        ordered = sorted(
            tracklets.values(),
            key=lambda tracklet: (
                tracklet.start_frame,
                tracklet.end_frame,
                tracklet.track_id,
            ),
        )
        costs = np.full((len(ordered), len(ordered)), _INVALID_COST, dtype=np.float64)

        for source_index, source in enumerate(ordered):
            for target_index in range(source_index + 1, len(ordered)):
                target = ordered[target_index]
                missed_frames = target.start_frame - source.end_frame - 1
                if missed_frames < 1 or missed_frames > self._max_gap:
                    continue
                if (
                    source.boxes[source.end_frame].label
                    != target.boxes[target.start_frame].label
                ):
                    continue

                cost = self._link_cost(source, target)
                if cost is not None:
                    costs[source_index, target_index] = cost

        rows, columns = linear_sum_assignment(costs)
        links = []
        for row, column in zip(rows, columns):
            cost = costs[row, column]
            if cost > _MAX_LINK_COST:
                continue
            row_alternatives = costs[row, :]
            column_alternatives = costs[:, column]
            row_alternatives = row_alternatives[
                (row_alternatives <= _MAX_LINK_COST)
                & (np.arange(len(ordered)) != column)
            ]
            column_alternatives = column_alternatives[
                (column_alternatives <= _MAX_LINK_COST)
                & (np.arange(len(ordered)) != row)
            ]
            if (
                (row_alternatives.size and np.min(row_alternatives) - cost <= _AMBIGUITY_MARGIN)
                or (
                    column_alternatives.size
                    and np.min(column_alternatives) - cost <= _AMBIGUITY_MARGIN
                )
            ):
                continue
            links.append((ordered[row].key, ordered[column].key))
        return links

    @staticmethod
    def _link_cost(source: _Tracklet, target: _Tracklet) -> float | None:
        """Compute a geometry and scale cost for temporally ordered tracklets.

        Args:
            source: Earlier tracklet with an observed endpoint.
            target: Later same-class tracklet with an observed start.

        Returns:
            A finite link cost or ``None`` when projected geometry is implausible.

        Raises:
            None.

        Note:
            Endpoint motion is projected in both directions to the shared temporal
            midpoint before GIoU is measured. Strong overlap allows scale ratios up
            to 3x for partial occlusion; weaker overlap is limited to 2x.

        Example:
            cost = TrackingPostProcessor._link_cost(earlier, later)
        """
        gap = target.start_frame - source.end_frame
        midpoint_offset = gap / 2.0
        source_end = np.asarray(source.boxes[source.end_frame].bbox_xyxy, dtype=np.float64)
        target_start = np.asarray(target.boxes[target.start_frame].bbox_xyxy, dtype=np.float64)
        # Project the earlier endpoint forward and later endpoint backward to the
        # same midpoint; e.g. frames 10 and 16 project toward frame 13, reducing
        # the impact of an irregular detector gap on the identity comparison.
        source_mid = source_end + source.velocity(at_end=True) * midpoint_offset
        target_mid = target_start - target.velocity(at_end=False) * midpoint_offset
        giou = _generalized_iou(source_mid, target_mid)
        if giou <= 0.0:
            return None

        area_source = _area(source_mid)
        area_target = _area(target_mid)
        area_ratio = (
            max(area_source, area_target) / min(area_source, area_target)
            if min(area_source, area_target) > 0.0
            else float("inf")
        )
        # A clear midpoint match can tolerate a 3x box-area shift caused by partial
        # occlusion; without strong GIoU, constrain scale changes to avoid ID swaps.
        if area_ratio > (3.0 if giou >= 0.5 else 2.0):
            return None
        area_similarity = (
            min(area_source, area_target) / max(area_source, area_target)
            if max(area_source, area_target) > 0.0
            else 0.0
        )
        geometry_cost = (1.0 - giou) / 2.0
        return 0.8 * geometry_cost + 0.2 * (1.0 - area_similarity)

    @staticmethod
    def _fill_gap(
        output: ListOfBoxesByFrameIndexAsDict,
        source: _Tracklet,
        target: _Tracklet,
        template: BBoxViewModel,
        smoothness: float,
    ) -> int:
        """Interpolate missing frames with two endpoint predictions and GSI weights.

        Args:
            output: Mutable output frame map.
            source: Earlier detection-backed tracklet.
            target: Later detection-backed tracklet.
            template: Canonical identity box used for synthesized output.
            smoothness: Gaussian kernel lengthscale tau.

        Returns:
            Number of interpolated frames.

        Raises:
            None.

        Note:
            Each endpoint prediction is weighted by a Gaussian of its temporal
            distance; larger tau spreads influence more evenly through the gap.

        Example:
            count = TrackingPostProcessor._fill_gap(output, left, right, template, 10.0)
        """
        left_frame = source.end_frame
        right_frame = target.start_frame
        left_box = source.boxes[left_frame]
        right_box = target.boxes[right_frame]
        left_coords = np.asarray(left_box.bbox_xyxy, dtype=np.float64)
        right_coords = np.asarray(right_box.bbox_xyxy, dtype=np.float64)
        left_velocity = source.velocity(at_end=True)
        right_velocity = target.velocity(at_end=False)
        sigma = smoothness
        interpolated_count = 0

        for frame_index in range(left_frame + 1, right_frame):
            left_distance = frame_index - left_frame
            right_distance = right_frame - frame_index
            left_prediction = left_coords + left_velocity * left_distance
            right_prediction = right_coords - right_velocity * right_distance
            # Gaussian weights favor each endpoint's prediction according to
            # temporal distance; tau is user-configurable smoothness, e.g. tau=10
            # softens a 25-frame gap more gradually than tau=1.
            left_weight = math.exp(-0.5 * (left_distance / sigma) ** 2)
            right_weight = math.exp(-0.5 * (right_distance / sigma) ** 2)
            coords = (
                left_prediction * left_weight + right_prediction * right_weight
            ) / (left_weight + right_weight)
            x1, y1, x2, y2 = (int(round(value)) for value in coords)

            interpolated = template.clone()
            interpolated.bbox_xyxy = (x1, y1, max(x1, x2), max(y1, y2))
            interpolated.detection_backed = False
            interpolated.time_since_update = min(left_distance, right_distance)
            confidences = [
                confidence
                for confidence in (left_box.confidence, right_box.confidence)
                if confidence is not None
            ]
            if confidences:
                interpolated.confidence = min(confidences)
            output.setdefault(frame_index, []).append(interpolated)
            interpolated_count += 1
        return interpolated_count

    def _coast_box(
        self, tracklet: _Tracklet, age: int, template: BBoxViewModel
    ) -> BBoxViewModel | None:
        """Create one forward coast estimate and apply the configured decay.

        Args:
            tracklet: Detection-backed source segment.
            age: Consecutive missed-frame count for this estimate.
            template: Canonical identity and color source.

        Returns:
            A coasted clone, or ``None`` when confidence falls below the floor.

        Raises:
            None.

        Note:
            Unbridged offline estimates lose confidence at twice the standard
            rate and are separately capped by ``max_unbridged_coast``.

        Example:
            estimate = processor._coast_box(tracklet, age=2, template=box)
        """
        last_frame = tracklet.end_frame
        last_box = tracklet.boxes[last_frame]
        base_confidence = last_box.confidence if last_box.confidence is not None else 1.0
        decay_rate = self._confidence_decay * (
            2.0 if self._offline_stitching_enabled else 1.0
        )
        # Subtract once per missed frame; doubling the offline rate makes a
        # never-reconnected .9-confidence box fall to .3 after six misses at .05.
        confidence = max(0.0, base_confidence - decay_rate * age)
        if confidence < self._min_confidence:
            return None

        coords = np.asarray(last_box.bbox_xyxy, dtype=np.float64)
        velocity = tracklet.velocity(at_end=True)
        x1, y1, x2, y2 = (
            int(round(value))
            for value in coords + velocity * age
        )
        coast = template.clone()
        coast.bbox_xyxy = (x1, y1, max(x1, x2), max(y1, y2))
        coast.confidence = round(confidence, 4)
        coast.detection_backed = False
        coast.time_since_update = age
        return coast


def _area(box: np.ndarray) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _generalized_iou(box_a: np.ndarray, box_b: np.ndarray) -> float:
    intersection_x1 = max(box_a[0], box_b[0])
    intersection_y1 = max(box_a[1], box_b[1])
    intersection_x2 = min(box_a[2], box_b[2])
    intersection_y2 = min(box_a[3], box_b[3])
    intersection = max(0.0, intersection_x2 - intersection_x1) * max(
        0.0, intersection_y2 - intersection_y1
    )
    area_a = _area(box_a)
    area_b = _area(box_b)
    union = area_a + area_b - intersection
    if union <= 0.0:
        return -1.0

    iou = intersection / union
    enclosing_x1 = min(box_a[0], box_b[0])
    enclosing_y1 = min(box_a[1], box_b[1])
    enclosing_x2 = max(box_a[2], box_b[2])
    enclosing_y2 = max(box_a[3], box_b[3])
    enclosing = max(0.0, enclosing_x2 - enclosing_x1) * max(
        0.0, enclosing_y2 - enclosing_y1
    )
    if enclosing <= 0.0:
        return -1.0
    return float(iou - (enclosing - union) / enclosing)
