"""
Batch processing collaborator for worker-produced detection results.

See Also:
    - [`DetectionResult`][app.domain.detection.result.DetectionResult] — the per-frame result records processed here
    - [`DetectionExecutionService`][app.application.services.detection.execution.DetectionExecutionService] — runs inference that produces worker results

Layer: Application.
Context: Coordinates domain state and infrastructure to complete application use cases.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain import map_detections_to_bbox, new_passes_filter, VideoDataLayer, ProcessingSettings
from app.shared.logging_cfg import get_logger

if TYPE_CHECKING:
    from app.application.interfaces import UIApplicationInterface
    from app.infrastructure.session.session import Session
    from app.domain.detection.result import DetectionResult
    from app.domain.session import SessionId

logger = get_logger("Application->DetectionBatchProcessor")


@dataclass(slots=True)
class DetectionBatchProcessReport:
    """
    Batch counts; `written_boxes` counts filtered boxes retained in Layer A.

    Layer: Application.
    Context: Coordinates use-case behavior through domain services and application contracts.
    """

    total_frames: int
    skipped_existing_frames: int
    written_frames: int
    written_boxes: int


class DetectionBatchProcessor:
    """
    Store selected detections in Layer A and editable clones in Layer B.

    Working principle
        ```python
        session = get_session(s_id)
        for frame_index, raw_detections in batch:
            if session.has_boxes(Layer.A, frame_index):
                skip_frame()
                continue
            raw_boxes = map_detections_to_bbox(raw_detections)
            settings = get_session_settings(session)
            filtered_boxes = filter(raw_boxes, new_passes_filter, Layer.B, settings)
            session.add_boxes(Layer.A, frame_index, filtered_boxes)
            session.replace_machine_boxes(Layer.B, frame_index, filtered_boxes)
        return DetectionBatchProcessReport(...)
        ```


    Layer: Application.
    Context: Coordinates use-case behavior through domain services and application contracts.


    Args:
        session_repo: Interface used to retrieve a session and write its frame-indexed detections.
    """

    def __init__(self, session_repo: UIApplicationInterface) -> None:
        self._app_adapter = session_repo

    def process_batch(
            self, s_id: SessionId, batch: dict[int, list[DetectionResult]]
    ) -> DetectionBatchProcessReport:
        """
        Process batch.

        Args:
            s_id: Identifier of the session receiving the detection results.
            batch: Detection results keyed by zero-based frame index.

        Returns:
            Counts of frames received, frames written, skipped frames, and boxes written.
        """
        session = self._app_adapter.get_session_by_id(s_id)
        skipped_existing_frames = 0
        written_frames = 0
        written_boxes = 0

        for frame_index, raw_detections in batch.items():
            written_count = self._write_detections_if_frame_empty(session, frame_index, raw_detections)
            if written_count is None:
                skipped_existing_frames += 1
                continue

            written_frames += 1
            written_boxes += written_count

        logger.trace(
            "Processed detection batch for session '{}': total={} written={} skipped={} boxes={}",
            s_id,
            len(batch),
            written_frames,
            skipped_existing_frames,
            written_boxes,
        )
        return DetectionBatchProcessReport(
            total_frames=len(batch),
            skipped_existing_frames=skipped_existing_frames,
            written_frames=written_frames,
            written_boxes=written_boxes,
        )

    @staticmethod
    def _write_detections_if_frame_empty(
            session: Session, frame_index: int, raw_detections: list[DetectionResult]
    ) -> int | None:
        """
        Write selected detections to A and refresh machine boxes in B.

        Args:
            session: Session receiving detections.
            frame_index: Zero-based target frame.
            raw_detections: Raw model output for this frame.

        Returns:
            The number of filtered boxes written, or `None` when A already has boxes.

        Raises:
            AttributeError: If session settings are unavailable.
            Exception: Propagates storage or filtering failures.

        Note:
            Label and detection-confidence settings filter results before Layer A
            storage, matching the historical detection behavior. An empty label
            selection permits every class. Existing manual Layer B annotations
            are preserved by the storage replacement method; existing machine
            boxes are always refreshed.

        Example:
            count = DetectionBatchProcessor._write_detections_if_frame_empty(session, 0, detections)
        """
        source_layer = VideoDataLayer.A
        target_layer = VideoDataLayer.B
        if session.data.has_boxes_for_layer_at_frame_index(source_layer, frame_index):
            return None

        raw_boxes = map_detections_to_bbox(raw_detections)
        settings = DetectionBatchProcessor._get_session_settings(session)
        filtered_boxes = [box for box in raw_boxes if new_passes_filter(target_layer, box, settings)]
        logger.trace(
            "Detection selection for frame {}: labels={} min_confidence={} raw={} retained={}",
            frame_index,
            settings.chosen_labels,
            settings.min_detection_confidence,
            len(raw_boxes),
            len(filtered_boxes),
        )
        logger.debug(
            "Writing {} selected detection(s) to Layer A for frame {}",
            len(filtered_boxes), frame_index,
        )
        session.data.add_boxes_to_layer_at_frame_index(source_layer, frame_index, filtered_boxes)
        session.data.replace_machine_boxes_at_frame_index(
            target_layer, frame_index, filtered_boxes
        )
        return len(filtered_boxes)

    @staticmethod
    def _get_session_settings(session: Session) -> ProcessingSettings:
        settings = getattr(session.state, "settings", None)
        if isinstance(settings, ProcessingSettings):
            return settings

        legacy_settings = getattr(session.state, "session_settings", None)
        if isinstance(legacy_settings, ProcessingSettings):
            warnings.warn(
                "session.view_state.session_settings is deprecated; use session.view_state.settings instead.",
                DeprecationWarning,
                stacklevel=3,
            )
            return legacy_settings

        settings_type = type(settings).__name__
        legacy_settings_type = type(legacy_settings).__name__
        raise AttributeError(
            "Session view_state must expose ProcessingSettings via 'settings' or 'session_settings' "
            f"(got settings={settings_type}, session_settings={legacy_settings_type})."
        )
