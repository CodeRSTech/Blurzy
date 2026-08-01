"""Batch processing collaborator for worker-produced detection results."""

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
    total_frames: int
    skipped_existing_frames: int
    written_frames: int
    written_boxes: int


class DetectionBatchProcessor:
    """Process worker batches into filtered Layer A detections.

    Working principle
        .. code-block:: python

            session = get_session(s_id)
            for frame_index, raw_detections in batch:
                if session.has_boxes(Layer.A, frame_index):
                    skip_frame(); continue
                boxes = map_detections_to_bbox(raw_detections)
                settings = get_session_settings(session)
                boxes = filter(boxes, new_passes_filter, Layer.B, settings)
                session.add_boxes(Layer.A, frame_index, boxes)
            return DetectionBatchProcessReport(...)
    """

    def __init__(self, session_repo: UIApplicationInterface) -> None:
        self._app_adapter = session_repo

    def process_batch(
            self, s_id: SessionId, batch: dict[int, list[DetectionResult]]
    ) -> DetectionBatchProcessReport:
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
        source_layer = VideoDataLayer.A
        target_layer = VideoDataLayer.B
        if session.data.has_boxes_for_layer_at_frame_index(source_layer, frame_index):
            return None

        raw_boxes = map_detections_to_bbox(raw_detections)
        settings = DetectionBatchProcessor._get_session_settings(session)
        # filtered_boxes = [detection for detection in raw_boxes if passes_filter_for_layer_b(detection, session.state.settings)]
        filtered_boxes = [box for box in raw_boxes if new_passes_filter(target_layer, box, settings)]
        session.data.add_boxes_to_layer_at_frame_index(source_layer, frame_index, filtered_boxes)
        return len(filtered_boxes)

    @staticmethod
    def _get_session_settings(session: Session) -> ProcessingSettings:
        settings = getattr(session.state, "settings", None)
        if isinstance(settings, ProcessingSettings):
            return settings

        legacy_settings = getattr(session.state, "session_settings", None)
        if isinstance(legacy_settings, ProcessingSettings):
            warnings.warn(
                "session.state.session_settings is deprecated; use session.state.settings instead.",
                DeprecationWarning,
                stacklevel=3,
            )
            return legacy_settings

        settings_type = type(settings).__name__
        legacy_settings_type = type(legacy_settings).__name__
        raise AttributeError(
            "Session state must expose ProcessingSettings via 'settings' or 'session_settings' "
            f"(got settings={settings_type}, session_settings={legacy_settings_type})."
        )
