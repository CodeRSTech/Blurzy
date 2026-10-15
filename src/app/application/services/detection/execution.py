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
        """Detect the current frame and refresh its raw and editable layers.

        Args:
            s_id: Session identifier whose current frame is processed.

        Returns:
            None.

        Raises:
            Exception: Propagates model, filtering, and storage failures.

        Note:
            The raw Layer A output is retained, while Layer B machine boxes are
            replaced even when the frame was initialized earlier; manual boxes survive.

        Example:
            service.execute_for_current_frame(session_id)
        """
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

        frame_index = session.state.playback.current_frame_index
        session.data.add_boxes_to_layer_at_frame_index(VideoDataLayer.A, frame_index, raw_boxes)
        session.data.replace_machine_boxes_at_frame_index(
            VideoDataLayer.B, frame_index, filtered
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
        return [box for box in boxes if new_passes_filter(VideoDataLayer.B, box, settings)]
