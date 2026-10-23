"""
Single-frame detection execution collaborator.

See Also:
    - [`DetectionEngineManager`][app.application.managers.detection_engine.DetectionEngineManager] — supplies session detection engines
    - [`DetectionBatchProcessor`][app.application.services.detection.batch_processor.DetectionBatchProcessor] — processes worker-produced results

Layer: Application.
Context: Coordinates domain state and infrastructure to complete application use cases.
"""

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
    """
    Run current-frame detection while delegating engine lifecycle to the manager.

    Layer: Application.
    Context: Coordinates use-case behavior through domain services and application contracts.


    Args:
        session_repo: Interface used to retrieve the session and its current frame for inference.
        engine_manager: Manager responsible for detection-engine lifecycle.
    """

    def __init__(
            self, session_repo: UIApplicationInterface, engine_manager: DetectionEngineManager
    ) -> None:
        self._app_adapter = session_repo
        self._engine_manager = engine_manager

    def execute_for_current_frame(self, s_id: SessionId) -> None:
        """
        Detect the current frame and refresh its selected and editable detections.

        Args:
            s_id: Session identifier whose current frame is processed.
        Raises:
            Exception: Propagates model, filtering, and storage failures.

        Note:
            Label and detection-confidence settings filter model output before
            Layer A storage. An empty label selection permits every class.
            Layer B machine boxes are replaced even when the frame was initialized
            earlier; manual boxes survive.

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
        logger.debug(
            "Writing {} selected detection(s) to Layer A for session '{}' frame {}",
            len(filtered), s_id, frame_index,
        )
        session.data.add_boxes_to_layer_at_frame_index(VideoDataLayer.A, frame_index, filtered)
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
        """
        Apply the historical detection selection before storing either layer.

        Args:
            boxes: Mapped model detections.
            settings: Selected labels and detection-confidence threshold.

        Returns:
            Boxes accepted by the Layer B detection predicate.


        Note:
            Layer A also uses this predicate at the detection storage boundary;
            an empty label list disables class restriction.

        Example:
            selected = DetectionExecutionService._filter_boxes(boxes, settings)
        """
        filtered = [box for box in boxes if new_passes_filter(VideoDataLayer.B, box, settings)]
        logger.trace(
            "Detection selection: labels={} min_confidence={} raw={} retained={}",
            settings.chosen_labels,
            settings.min_detection_confidence,
            len(boxes),
            len(filtered),
        )
        return filtered
