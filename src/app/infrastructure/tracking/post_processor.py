"""Offline tracklet stitching and bounded Gaussian interpolation.

Layer: Infrastructure.
Context: Implements concrete processing and I/O behind application-facing contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import TYPE_CHECKING

import numpy as np
from scipy.optimize import linear_sum_assignment

from app.domain.views import BBoxViewModel
from app.infrastructure.tracking.reid_extractor import cosine_similarity
from app.shared.logging_cfg import get_logger

if TYPE_CHECKING:
    from app.domain.base.dtypes import ListOfBoxesByFrameIndexAsDict

logger = get_logger("Infrastructure->Tracking->PostProcessor")

_INVALID_COST = 1_000_000.0
_MAX_LINK_COST = 0.35
# Reject near-tied assignments when the second choice is within five cost points.
_AMBIGUITY_MARGIN = 0.05


def _normalized_mean(vectors: list[np.ndarray]) -> np.ndarray | None:
    """Return the normalized mean of available embedding vectors."""
    if not vectors:
        return None
    mean = np.mean(np.stack(vectors).astype(np.float32), axis=0)
    norm = float(np.linalg.norm(mean))
    return mean / max(norm, 1e-8)


@dataclass(slots=True)
class _Tracklet:
    key: tuple[str, int]
    track_id: str
    boxes: dict[int, BBoxViewModel]
    head_embedding: np.ndarray | None = None
    tail_embedding: np.ndarray | None = None

    @property
    def frames(self) -> list[int]:
        """Return the sorted frame indices containing observations.

        Returns:
            Observed frame indices for this tracklet.
        """
        return sorted(self.boxes)

    @property
    def start_frame(self) -> int:
        """Return the first observed frame index.

        Returns:
            Earliest frame containing an observation.
        """
        return min(self.boxes)

    @property
    def end_frame(self) -> int:
        """Return the last observed frame index.

        Returns:
            Latest frame containing an observation.
        """
        return max(self.boxes)

    def velocity(self, *, at_end: bool, window: int = 5) -> np.ndarray:
        """Estimate box-coordinate velocity near a tracklet endpoint.

        Args:
            at_end: Use final observations when true; otherwise use initial ones.
            window: Maximum number of endpoint observations to use.

        Returns:
            Mean coordinate displacement per elapsed frame in `xyxy` order.
        """
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
        privacy_features_enabled: Whether conservative privacy post-processing is active.
        resist_box_shrinking: Whether output boxes resist sudden contractions.
        shrink_resistance: Damping factor for decreasing the box envelope.
        pre_detection_padding_sec: Duration of backward box extrapolation.
        post_detection_padding_sec: Duration of forward box holding.
        box_safety_padding_pct: Proportional outward box inflation.
        fps: Video frame rate used to convert padding durations to frames.
        frame_width: Optional frame width used to clamp projected boxes.
        frame_height: Optional frame height used to clamp projected boxes.

    Raises:
        ValueError: If any numeric setting is outside its supported range.

    Note:
        With offline stitching enabled, coasted input boxes are discarded in favor
        of detection-backed observations, stitched GSI gaps, and short 2x-decay
        tails. With stitching disabled, missing frames use causal 1x-decay estimates.

    Example:
        processor = TrackingPostProcessor(max_gap=25, gsi_smoothness=10.0)
        results = processor.process(track_data, total_frames=300)


Layer: Infrastructure.
Context: Implements concrete processing or I/O behind application-facing contracts.
"""

    def __init__(
        self,
        max_gap: int = 25,
        gsi_smoothness: float = 10.0,
        confidence_decay: float = 0.05,
        min_confidence: float = 0.1,
        offline_stitching_enabled: bool = True,
        max_unbridged_coast: int = 6,
        privacy_features_enabled: bool = False,
        resist_box_shrinking: bool = True,
        shrink_resistance: float = 0.85,
        pre_detection_padding_sec: float = 0.5,
        post_detection_padding_sec: float = 0.5,
        box_safety_padding_pct: float = 0.10,
        fps: float = 30.0,
        frame_width: int = 0,
        frame_height: int = 0,
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
        if not 0.0 <= shrink_resistance <= 0.99:
            raise ValueError("shrink_resistance must be between 0.0 and 0.99.")
        if not 0.0 <= pre_detection_padding_sec <= 5.0:
            raise ValueError("pre_detection_padding_sec must be between 0.0 and 5.0 seconds.")
        if not 0.0 <= post_detection_padding_sec <= 5.0:
            raise ValueError("post_detection_padding_sec must be between 0.0 and 5.0 seconds.")
        if not 0.0 <= box_safety_padding_pct <= 0.50:
            raise ValueError("box_safety_padding_pct must be between 0.0 and 0.50.")
        if frame_width < 0 or frame_height < 0:
            raise ValueError("frame dimensions must be non-negative.")
        self._privacy_features_enabled = privacy_features_enabled
        self._resist_box_shrinking = resist_box_shrinking
        self._shrink_resistance = shrink_resistance
        self._pre_detection_padding_sec = pre_detection_padding_sec
        self._post_detection_padding_sec = post_detection_padding_sec
        self._box_safety_padding_pct = box_safety_padding_pct
        self._fps = fps if math.isfinite(fps) and fps > 0 else 30.0
        self._frame_width = frame_width
        self._frame_height = frame_height

    def process(
        self,
        tracked_data: ListOfBoxesByFrameIndexAsDict,
        total_frames: int | None = None,
        appearance_embeddings_by_frame: dict[int, dict[str, np.ndarray]] | None = None,
    ) -> ListOfBoxesByFrameIndexAsDict:
        """Post-process observations into stitched or causal tracking output.

        Args:
            tracked_data: Tracker output keyed by zero-based frame index.
            total_frames: Optional video frame count used to bound final coast tails.
            appearance_embeddings_by_frame: Optional isolated appearance vectors keyed
                by frame index and tracker box ID.

        Returns:
            A sorted frame-to-box mapping containing observations and accepted coasts.

        Raises:
            ValueError: If `total_frames` is negative.

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
        tracklets, segment_by_observation = self._extract_tracklets(
            observations,
            appearance_embeddings_by_frame=appearance_embeddings_by_frame,
        )
        links = self._assign_links(tracklets) if self._offline_stitching_enabled else []

        predecessors = {target: source for source, target in links}

        def root_key(key: tuple[str, int]) -> tuple[str, int]:
            """Follow predecessor links to the earliest tracklet in a chain.

            Args:
                key: Key identifying the starting tracklet.

            Returns:
                Key of the chain's root tracklet.
            """
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
        if self._privacy_features_enabled:
            output = self._apply_privacy_features(output, final_frame_count)

        logger.debug(
            "Offline tracking post-processing linked {} tracklet pair(s) across {} frame(s)",
            len(links),
            interpolated_count,
        )
        return dict(sorted(output.items()))

    def _apply_privacy_features(
        self,
        output: ListOfBoxesByFrameIndexAsDict,
        total_frames: int,
    ) -> ListOfBoxesByFrameIndexAsDict:
        """Apply size protection, temporal padding, and safety inflation.

        Args:
            output: Stitched boxes keyed by zero-based frame index.
            total_frames: Exclusive end of the available frame range.

        Returns:
            A privacy-adjusted frame mapping with cloned boxes.

        Note:
            The size envelope expands immediately and contracts only by
            `rho * envelope + (1 - rho) * observation` when resistance is on.
            Pre/post motion is estimated from at most five observed box centers,
            clamped to one quarter of the envelope per frame, and damped by
            $0.85^k$ for each projected step.
            A safety proportion `p` expands a box of width `w` and height
            `h` by `p*w` and `p*h` respectively, split evenly around the
            center before clipping to known frame bounds.

        Example:
            safe_tracks = processor._apply_privacy_features(tracks, 300)
        """
        output = {
            frame_index: [box.clone() for box in boxes]
            for frame_index, boxes in output.items()
        }
        by_track: dict[str, list[tuple[int, BBoxViewModel]]] = {}
        for frame_index, boxes in output.items():
            for box in boxes:
                by_track.setdefault(box.id, []).append((frame_index, box))

        envelopes: dict[str, tuple[float, float]] = {}
        observations_by_track: dict[str, list[tuple[int, BBoxViewModel]]] = {}
        for track_id, entries in by_track.items():
            entries.sort(key=lambda entry: entry[0])
            detections = [
                (frame_index, box)
                for frame_index, box in entries
                if box.detection_backed and box.time_since_update == 0
            ]
            if not detections:
                continue
            observations_by_track[track_id] = detections
            first_box = detections[0][1]
            envelope_width = float(max(1, first_box.bbox_xyxy[2] - first_box.bbox_xyxy[0]))
            envelope_height = float(max(1, first_box.bbox_xyxy[3] - first_box.bbox_xyxy[1]))
            previous_box: BBoxViewModel | None = None

            for _, box in entries:
                x1, y1, x2, y2 = box.bbox_xyxy
                current_width = float(max(1, x2 - x1))
                current_height = float(max(1, y2 - y1))
                # Expand immediately when a detection grows; otherwise blend
                # only the observed shrink fraction into the running envelope.
                if current_width > envelope_width:
                    envelope_width = current_width
                elif self._resist_box_shrinking:
                    envelope_width = (
                        self._shrink_resistance * envelope_width
                        + (1.0 - self._shrink_resistance) * current_width
                    )

                if current_height > envelope_height:
                    envelope_height = current_height
                elif self._resist_box_shrinking:
                    envelope_height = (
                        self._shrink_resistance * envelope_height
                        + (1.0 - self._shrink_resistance) * current_height
                    )

                if self._resist_box_shrinking:
                    center_x = (x1 + x2) / 2.0
                    target_width = max(current_width, envelope_width)
                    x1 = int(round(center_x - target_width / 2.0))
                    x2 = int(round(center_x + target_width / 2.0))

                    if previous_box is None:
                        center_y = (y1 + y2) / 2.0
                        y1 = int(round(center_y - envelope_height / 2.0))
                        y2 = int(round(center_y + envelope_height / 2.0))
                    else:
                        _, previous_y1, _, previous_y2 = previous_box.bbox_xyxy
                        top_shift = y1 - previous_y1
                        bottom_shift = y2 - previous_y2
                        current_height = y2 - y1
                        # When the bottom edge moves upward farther than the
                        # head/top edge, keep the top fixed and extend downward;
                        # reverse the anchor when only the top edge drops.
                        if bottom_shift < 0 and abs(bottom_shift) > abs(top_shift):
                            y2 = int(round(y1 + envelope_height))
                        elif top_shift > 0 and abs(top_shift) > abs(bottom_shift):
                            y1 = int(round(y2 - envelope_height))
                        else:
                            center_y = (y1 + y2) / 2.0
                            y1 = int(round(center_y - envelope_height / 2.0))
                            y2 = int(round(center_y + envelope_height / 2.0))
                    box.bbox_xyxy = self._clamp_box((x1, y1, x2, y2))
                previous_box = box
            envelopes[track_id] = (envelope_width, envelope_height)

        # Convert seconds to nearest frames using the resolved positive FPS.
        pre_frames = int(round(self._pre_detection_padding_sec * self._fps))
        post_frames = int(round(self._post_detection_padding_sec * self._fps))
        for track_id, detections in observations_by_track.items():
            envelope_width, envelope_height = envelopes[track_id]
            first_frame, first_box = detections[0]
            first_velocity = self._privacy_velocity(detections, at_end=False)
            x1, y1, x2, y2 = first_box.bbox_xyxy
            center_x = (x1 + x2) / 2.0
            center_y = (y1 + y2) / 2.0
            for age in range(1, min(pre_frames, first_frame) + 1):
                # Reverse velocity is damped per step; summing these increments
                # avoids extending a noisy entry velocity at constant speed.
                damping = 0.85**age
                center_x -= first_velocity[0] * damping
                center_y -= first_velocity[1] * damping
                if self._center_outside_frame(center_x, center_y):
                    break
                # Use the track envelope, not a small partial-body endpoint box.
                projected = self._clamp_box(
                    (
                        int(round(center_x - envelope_width / 2.0)),
                        int(round(center_y - envelope_height / 2.0)),
                        int(round(center_x + envelope_width / 2.0)),
                        int(round(center_y + envelope_height / 2.0)),
                    )
                )
                frame_index = first_frame - age
                confidence = self._padding_confidence(first_box, age, pre_frames)
                self._insert_padding_box(
                    output, frame_index, first_box, projected, confidence, age
                )

            last_frame, last_box = detections[-1]
            terminal_velocity = self._privacy_velocity(detections, at_end=True)
            x1, y1, x2, y2 = last_box.bbox_xyxy
            center_x = (x1 + x2) / 2.0
            center_y = (y1 + y2) / 2.0
            for age in range(1, min(post_frames, max(0, total_frames - last_frame - 1)) + 1):
                # Forward displacement also decays by $0.85^k$, so a stopped
                # subject cannot drift indefinitely along its last velocity.
                damping = 0.85**age
                center_x += terminal_velocity[0] * damping
                center_y += terminal_velocity[1] * damping
                if self._center_outside_frame(center_x, center_y):
                    break
                # Hold the envelope dimensions while the damped center advances.
                projected = self._clamp_box(
                    (
                        int(round(center_x - envelope_width / 2.0)),
                        int(round(center_y - envelope_height / 2.0)),
                        int(round(center_x + envelope_width / 2.0)),
                        int(round(center_y + envelope_height / 2.0)),
                    )
                )
                frame_index = last_frame + age
                confidence = self._padding_confidence(last_box, age, post_frames)
                self._insert_padding_box(
                    output, frame_index, last_box, projected, confidence, age
                )

        if self._box_safety_padding_pct > 0.0:
            for boxes in output.values():
                for box in boxes:
                    x1, y1, x2, y2 = box.bbox_xyxy
                    width = max(1, x2 - x1)
                    height = max(1, y2 - y1)
                    # Split the proportional width/height increase evenly around
                    # the center before clipping to frame edges.
                    pad_x = width * self._box_safety_padding_pct / 2.0
                    pad_y = height * self._box_safety_padding_pct / 2.0
                    center_x = (x1 + x2) / 2.0
                    center_y = (y1 + y2) / 2.0
                    box.bbox_xyxy = self._clamp_box(
                        (
                            int(round(center_x - width / 2.0 - pad_x)),
                            int(round(center_y - height / 2.0 - pad_y)),
                            int(round(center_x + width / 2.0 + pad_x)),
                            int(round(center_y + height / 2.0 + pad_y)),
                        )
                    )
        return output

    def _privacy_velocity(
        self,
        detections: list[tuple[int, BBoxViewModel]],
        *,
        at_end: bool,
    ) -> tuple[float, float]:
        """Estimate and clamp center velocity from up to five detections.

        Args:
            detections: Ordered detection-backed observations for one track.
            at_end: Whether to use the terminal rather than initial observations.

        Returns:
            Median per-frame center displacement, clamped to one quarter of the
            corresponding envelope dimension.

        Example:
            vx, vy = processor._privacy_velocity(detections, at_end=True)
        """
        sample = detections[-5:] if at_end else detections[:5]
        if len(sample) < 2:
            return 0.0, 0.0
        velocities: list[tuple[float, float]] = []
        for (frame_a, box_a), (frame_b, box_b) in zip(sample, sample[1:]):
            elapsed = frame_b - frame_a
            if elapsed <= 0:
                continue
            ax1, ay1, ax2, ay2 = box_a.bbox_xyxy
            bx1, by1, bx2, by2 = box_b.bbox_xyxy
            velocities.append(
                (
                    ((bx1 + bx2 - ax1 - ax2) / 2.0) / elapsed,
                    ((by1 + by2 - ay1 - ay2) / 2.0) / elapsed,
                )
            )
        if not velocities:
            return 0.0, 0.0
        velocity = np.median(np.asarray(velocities, dtype=np.float64), axis=0)
        ref_box = sample[-1 if at_end else 0][1]
        x1, y1, x2, y2 = ref_box.bbox_xyxy
        max_x = max(1.0, (x2 - x1) * 0.25)
        max_y = max(1.0, (y2 - y1) * 0.25)
        return (
            float(np.clip(velocity[0], -max_x, max_x)),
            float(np.clip(velocity[1], -max_y, max_y)),
        )

    def _padding_confidence(
        self,
        source: BBoxViewModel,
        age: int,
        total_padding: int,
    ) -> float:
        """Return a gradual padding confidence no lower than the configured floor.

        Args:
            source: Endpoint observation used to seed the padding box.
            age: Distance from the detection endpoint in frames.
            total_padding: Configured pre/post padding length in frames.

        Returns:
            A confidence that remains eligible for the tracking output floor.

        Note:
            With endpoint confidence `c0`, age `k`, and configured padding
            length `N`, the returned value is
            `round(max(min(1, min_confidence + 0.001), c0 * (1 - 0.25*k/max(1, N))), 4)`.

        Example:
            confidence = processor._padding_confidence(box, age=2, total_padding=10)
        """
        base = source.confidence if source.confidence is not None else 1.0
        floor = min(1.0, self._min_confidence + 0.001)
        decay = 0.25 * age / max(1, total_padding)
        return round(max(floor, base * (1.0 - decay)), 4)

    def _insert_padding_box(
        self,
        output: ListOfBoxesByFrameIndexAsDict,
        frame_index: int,
        source: BBoxViewModel,
        bbox: tuple[int, int, int, int],
        confidence: float,
        age: int,
    ) -> None:
        """Insert a cloned temporal padding box unless that track already exists.

        Args:
            output: Mutable output frame mapping.
            frame_index: Destination video frame.
            source: Track identity and style template.
            bbox: Projected and clamped rectangle.
            confidence: Confidence assigned to the synthetic box.
            age: Number of frames from the nearest observed endpoint.

        Example:
            processor._insert_padding_box(output, 14, box, rect, 0.8, 1)
        """
        boxes = output.setdefault(frame_index, [])
        padded = source.clone()
        padded.bbox_xyxy = bbox
        padded.confidence = confidence
        padded.detection_backed = False
        padded.time_since_update = age
        for index, existing in enumerate(boxes):
            if existing.id != source.id:
                continue
            if existing.detection_backed and existing.time_since_update == 0:
                return
            # Replace a generic coast with the privacy projection so it retains
            # the track's conservative envelope and damped terminal velocity.
            boxes[index] = padded
            return
        boxes.append(padded)

    def _clamp_box(
        self,
        bbox: tuple[int, int, int, int],
    ) -> tuple[int, int, int, int]:
        """Clamp a rectangle to non-negative coordinates and known frame bounds.

        Args:
            bbox: Candidate rectangle in xyxy pixel coordinates.

        Returns:
            A non-negative rectangle clipped to available frame dimensions.

        Example:
            safe_box = processor._clamp_box((-2, 1, 12, 14))
        """
        x1, y1, x2, y2 = bbox
        x1, y1 = max(0, x1), max(0, y1)
        if self._frame_width > 0:
            x1, x2 = min(x1, self._frame_width), min(x2, self._frame_width)
        if self._frame_height > 0:
            y1, y2 = min(y1, self._frame_height), min(y2, self._frame_height)
        return x1, y1, max(x1, x2), max(y1, y2)

    def _center_outside_frame(self, center_x: float, center_y: float) -> bool:
        """Return whether a projected center lies outside known frame bounds.

        Args:
            center_x: Projected horizontal center in pixels.
            center_y: Projected vertical center in pixels.

        Returns:
            True only when a known frame boundary is crossed.

        Example:
            outside = processor._center_outside_frame(500.0, 20.0)
        """
        return (
            (self._frame_width > 0 and not 0 <= center_x <= self._frame_width)
            or (self._frame_height > 0 and not 0 <= center_y <= self._frame_height)
        )

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
        appearance_embeddings_by_frame: dict[int, dict[str, np.ndarray]] | None = None,
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
                vectors = [
                    appearance_embeddings_by_frame[frame][track_id]
                    for frame in segment_frames
                    if appearance_embeddings_by_frame is not None
                    and track_id in appearance_embeddings_by_frame.get(frame, {})
                ]
                head_embedding = _normalized_mean(vectors[:3])
                tail_embedding = _normalized_mean(vectors[-3:])
                tracklets[key] = _Tracklet(
                    key=key,
                    track_id=track_id,
                    boxes={frame: observations[frame] for frame in segment_frames},
                    head_embedding=head_embedding,
                    tail_embedding=tail_embedding,
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

    def _link_cost(self, source: _Tracklet, target: _Tracklet) -> float | None:
        """Compute a geometry and scale cost for temporally ordered tracklets.

        Args:
            source: Earlier tracklet with an observed endpoint.
            target: Later same-class tracklet with an observed start.

        Returns:
            A finite link cost or `None` when projected geometry is implausible.


        Note:
            Endpoint motion is projected in both directions to the shared temporal
            midpoint before GIoU is measured. Strong overlap allows scale ratios
            up to 3x normally; privacy or anti-shrink mode relaxes the area gate
            to 6x so full-body and partial-body fragments can reconnect.

        Example:
            cost = processor._link_cost(earlier, later)
        """
        appearance_similarity: float | None = None
        if source.tail_embedding is not None and target.head_embedding is not None:
            appearance_similarity = cosine_similarity(source.tail_embedding, target.head_embedding)
            if appearance_similarity < 0.45:
                return None

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
        strong_appearance = appearance_similarity is not None and appearance_similarity >= 0.75
        if giou <= 0.0 and not strong_appearance:
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
        max_area_ratio = (
            6.0
            if self._privacy_features_enabled or self._resist_box_shrinking
            else (3.0 if giou >= 0.5 or strong_appearance else 2.0)
        )
        if area_ratio > max_area_ratio:
            return None
        area_similarity = (
            min(area_source, area_target) / max(area_source, area_target)
            if max(area_source, area_target) > 0.0
            else 0.0
        )
        geometry_cost = (1.0 - giou) / 2.0
        if strong_appearance:
            # Strong appearance continuity can overcome a poor linear midpoint
            # projection after a turn or reversal, while size consistency remains.
            return (
                0.10 * geometry_cost
                + 0.50 * (1.0 - appearance_similarity)
                + 0.15 * (1.0 - area_similarity)
            )
        if appearance_similarity is not None:
            return (
                0.65 * geometry_cost
                + 0.20 * (1.0 - appearance_similarity)
                + 0.15 * (1.0 - area_similarity)
            )
        return 0.8 * geometry_cost + 0.2 * (1.0 - area_similarity)

    @staticmethod
    def _fill_gap(
        output: ListOfBoxesByFrameIndexAsDict,
        source: _Tracklet,
        target: _Tracklet,
        template: BBoxViewModel,
        smoothness: float,
    ) -> int:
        r"""Interpolate missing frames with two endpoint predictions and GSI weights.

        Args:
            output: Mutable output frame map.
            source: Earlier detection-backed tracklet.
            target: Later detection-backed tracklet.
            template: Canonical identity box used for synthesized output.
            smoothness: Gaussian kernel lengthscale tau.

        Returns:
            Number of interpolated frames.


        Note:
            For an interpolated frame $f$, let $f_L$ and $f_R$ be the
            endpoint frame indices. The temporal distances and constant-velocity
            endpoint predictions are

            $$
            d_L = f - f_L,\quad d_R = f_R - f,\qquad
            \mathbf{p}_L = \mathbf{b}_L + d_L\mathbf{v}_L,\quad
            \mathbf{p}_R = \mathbf{b}_R - d_R\mathbf{v}_R.
            $$

            With smoothness lengthscale $\tau$, the Gaussian endpoint weights
            and per-coordinate blend are

            $$
            w_L = \exp\!\left(-\frac{1}{2}\left(\frac{d_L}{\tau}\right)^2\right),
            \quad
            w_R = \exp\!\left(-\frac{1}{2}\left(\frac{d_R}{\tau}\right)^2\right),
            \qquad
            \mathbf{b}(f) =
            \frac{w_L\mathbf{p}_L + w_R\mathbf{p}_R}{w_L+w_R}.
            $$

            Here $\mathbf{b}_L$ and $\mathbf{b}_R$ are endpoint `xyxy`
            coordinates, and $\mathbf{v}_L$ and $\mathbf{v}_R$ are their
            estimated coordinate velocities. Larger $\tau$ makes the weights
            decay more gradually with temporal distance.

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
            A coasted clone, or `None` when confidence falls below the floor.


        Note:
            Unbridged offline estimates lose confidence at twice the standard
            rate and are separately capped by `max_unbridged_coast`.
            For base confidence `c0` and missed-frame age `k`, confidence is
            `max(0, c0 - lambda*k)`, with `lambda` equal to
            `confidence_decay` or twice that value when offline stitching is on.

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
