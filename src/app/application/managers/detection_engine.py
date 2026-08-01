"""Centralizes detection engine lifecycle (create / update / remove) per session."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.infrastructure.detection.engine import DetectionEngineAdapterFactory
from app.shared.logging_cfg import get_logger

if TYPE_CHECKING:
    from app.application.interfaces import UIApplicationInterface
    from app.domain.session import SessionId

logger = get_logger("Application->DetectionEngineManager")


class DetectionEngineManager:
    """
    Manages the lifecycle of ``DetectionEngine`` instances on a per-session basis.

    Responsibilities:
        - Create a new ``DetectionEngine`` when none exists for a session.
        - Update the loaded model in an existing ``DetectionEngine``.
        - Remove (clear) the engine reference from a session.

    This manager centralises the engine-creation logic that previously lived
    inside ``DetectionService._create_or_update_detection_engine_from_model_name_for_session_id``,
    giving ``DetectionService`` a narrower single responsibility.

    The session repository is injected, so the manager is independently
    unit-testable without a live ``Application`` instance.
    """

    def __init__(self, session_repo: UIApplicationInterface) -> None:
        self._app_adapter = session_repo
        self._detection_engine_factory = DetectionEngineAdapterFactory()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"

    def create_or_update(self, s_id: SessionId, model_name: str) -> None:
        """
        Create a new engine or update the model in an existing engine for ``s_id``.

        Args:
            s_id: Session ID of the target session.
            model_name: YOLO model name to load (e.g. ``"yolov8n"``).

        Note:
            If the session has no engine yet, a new ``DetectionEngine`` is
            instantiated and assigned to ``session.detection_engine``.
            If an engine already exists, its model is updated via
            ``DetectionEngine.set_model()`` to avoid unnecessary re-creation.

            ``DetectionEngine`` is imported lazily to keep this module free of
            heavy infrastructure dependencies at import time.
        """
        session = self._app_adapter.get_session_by_id(s_id)

        if session.detection_engine is None:
            session.detection_engine = self._detection_engine_factory.create(model_name=model_name)
            logger.trace("Created detection engine for session '{}' with model {}.", s_id, model_name)
        else:
            session.detection_engine.set_model(model_name)
            logger.trace("Updated detection engine for session '{}' with model {}.", s_id, model_name)

    def remove(self, s_id: SessionId) -> None:
        """
        Remove (clear) the detection engine reference for ``s_id``.

        Args:
            s_id: Session ID of the target session.

        Note:
            Sets ``session.detection_engine`` to ``None``.  Any in-flight
            worker using that engine must be stopped before calling this.
        """
        session = self._app_adapter.get_session_by_id(s_id)
        session.detection_engine = None
        logger.trace("Removed detection engine for session '{}'.", s_id)
