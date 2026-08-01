"""Centralizes tracking worker lifecycle transitions per session."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain import VideoDataLayer
from app.shared.exceptions import (
    EmptyLayerException,
    TrackingWorkerAlreadyRunningException,
    TrackingWorkerNotFoundException,
    UnsupportedLayerException,
)
from app.shared.logging_cfg import get_logger

if TYPE_CHECKING:
    from app.application.interfaces import (
        UIApplicationInterface,
        TrackingWorkerFactoryInterface,
    )
    from app.domain.base.dtypes import ListOfBoxesByFrameIndexAsDict
    from app.domain.session import SessionId
    from app.infrastructure.session.session import Session

logger = get_logger("Application->TrackingWorkerManager")


class TrackingWorkerManager:
    """Canonical owner for tracking worker start/stop/switch transitions."""

    def __init__(
        self,
        app_adapter: UIApplicationInterface,
        worker_factory: TrackingWorkerFactoryInterface,
    ) -> None:
        self._app_adapter = app_adapter
        self._worker_factory = worker_factory

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"

    def start(self, s_id: SessionId, strategy_name: str, source_layer_name: str) -> None:
        session = self._app_adapter.get_session_by_id(s_id)

        if session.has_running_tracking_worker:
            raise TrackingWorkerAlreadyRunningException(
                message="Error while attempting to start tracking.",
                session_id=s_id,
            )

        source_layer_data = self._get_supported_source_layer_data(
            session=session,
            s_id=s_id,
            source_layer_name=source_layer_name,
        )
        if not source_layer_data:
            raise EmptyLayerException(
                "Error while attempting to start tracking.",
                layer_name=source_layer_name,
                session_id=s_id,
            )

        session.data.clear_layers_by_name([VideoDataLayer.C, VideoDataLayer.D])
        session.tracking_worker = self._worker_factory.create(
            strategy_name=strategy_name,
            source_data=source_layer_data,
            session_state=session.state,
        )
        logger.info(
            "Tracking worker started for session '{}' (strategy={}, source={})",
            s_id,
            strategy_name,
            source_layer_name,
        )

    def stop(self, s_id: SessionId) -> None:
        session = self._app_adapter.get_session_by_id(s_id)
        worker = session.tracking_worker

        if worker is None:
            return

        try:
            worker.stop()
        except ValueError as exc:
            logger.debug(
                "Ignoring transient tracking worker stop error for session '{}': {}",
                s_id,
                exc,
            )
            return

        session.tracking_worker = None
        logger.trace("Tracking worker stopped for session '{}'.", s_id)

    def switch_active_session(
        self,
        old_s_id: SessionId | None,
        new_s_id: SessionId,
        strategy_name: str,
        source_layer_name: str,
    ) -> None:
        if old_s_id is not None and old_s_id == new_s_id:
            logger.trace(
                "switch_active_session: old and new are the same ({}), skipping.",
                new_s_id,
            )
            return

        if old_s_id is not None:
            self.stop(old_s_id)

        self.start(new_s_id, strategy_name, source_layer_name)

    def get_tracked_data(self, s_id: SessionId) -> ListOfBoxesByFrameIndexAsDict:
        session = self._app_adapter.get_session_by_id(s_id)
        worker = session.tracking_worker
        if worker is None:
            raise TrackingWorkerNotFoundException(
                message="Tracking worker not found for syncing tracking cache.",
                session_id=s_id,
            )
        return worker.get_tracked_data()

    @staticmethod
    def _get_supported_source_layer_data(
        session: Session,
        s_id: SessionId,
        source_layer_name: str,
    ) -> ListOfBoxesByFrameIndexAsDict:
        if source_layer_name == VideoDataLayer.A or source_layer_name == VideoDataLayer.B:
            return session.get_layer_by_name(source_layer_name)

        raise UnsupportedLayerException(
            message="Error while attempting to start tracking.",
            source_layer_name=source_layer_name,
            session_id=s_id,
        )
