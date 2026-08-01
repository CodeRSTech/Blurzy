"""Single-frame detection execution collaborator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain import VideoDataLayer, map_detections_to_bbox, new_passes_filter
from app.shared.logging_cfg import get_logger

if TYPE_CHECKING:
    from app.application.interfaces import UIApplicationInterface
    from app.application.managers.detection_engine import DetectionEngineManager
    from app.domain.base.dtypes import ListOfBoxes
    from app.domain.export.processing_settings import ProcessingSettings
    from app.domain.session import SessionId
    from app.domain.views import BBoxViewModel
    from app.infrastructure.dtypes import RGBFrame
    from app.infrastructure.session.session import Session

logger = get_logger("Application->DetectionExecutionService")


class DetectionExecutionService:
    """Run current-frame detection while delegating engine lifecycle to the manager."""

    def __init__(
            self, session_repo: UIApplicationInterface, engine_manager: DetectionEngineManager
    ) -> None:
        self._app_adapter = session_repo
        self._engine_manager = engine_manager

    def execute_for_current_frame(self, s_id: SessionId) -> None:
        logger.info("Detecting objects in frame for session '{}'", s_id)
        session = self._app_adapter.get_session_by_id(s_id)

        if session.state.settings.model_name_is_null:
            logger.info("Detect current frame skipped: model is None")
            return

        if session.detection_engine is None:
            self._engine_manager.create_or_update(s_id, session.state.settings.detection_model_name)

        frame = self._get_current_frame_or_none(session)
        if frame is None:
            return

        raw_detections = session.detection_engine.detect(frame)
        raw_boxes = map_detections_to_bbox(raw_detections)
        filtered = self._filter_boxes(raw_boxes, session.state.settings)

        session.data.add_boxes_to_layer_at_frame_index(
            VideoDataLayer.A, session.state.playback.current_frame_index, filtered
        )

        logger.info(
            "Detected {} item(s) (after filter) for session '{}' frame {}",
            len(filtered),
            s_id,
            session.state.playback.current_frame_index,
        )

    @staticmethod
    def _get_current_frame_or_none(session: Session) -> RGBFrame | None:
        frame = session.get_current_frame()
        if frame is None:
            logger.warning(
                "Detection skipped: frame {} could not be decoded",
                session.state.playback.current_frame_index,
            )
        return frame

    @staticmethod
    def _filter_boxes(
            boxes: ListOfBoxes, settings: ProcessingSettings
    ) -> list[BBoxViewModel]:
        # [AUDIT] AMBIGUITY: This filters raw detection output (Layer A) but uses DataLayer.B
        # layer_name = DataLayer.B is semantically incorrect for raw detections.
        # These boxes come from detect_engine (Layer A raw output) but are filtered using Layer B thresholds.
        # Clarify intent: Is this pre-filtering before Layer A assignment (should use Layer A)?
        # Or intentionally using Layer B thresholds? If latter, document why.
        # Current code: layer_name = DataLayer.B (uses detection confidence, not tracker confidence)
        layer_name = VideoDataLayer.B
        return [box for box in boxes if new_passes_filter(layer_name, box, settings)]
