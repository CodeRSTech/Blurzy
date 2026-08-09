"""Tracking worker orchestration and multi-object tracking management."""

from __future__ import annotations

from typing import final, TYPE_CHECKING

from app.application.adapters import (
    ApplicationAdapter,
    TrackingWorkerFactoryAdapter,
)
from app.application.managers.tracking_worker import TrackingWorkerManager
from app.application.services.tracking.result_processor import TrackingResultProcessor
from app.domain import VideoDataLayer
from app.shared import get_logger
from app.shared.exceptions import (
    InvalidSessionIdException, EmptyLayerException,
)

if TYPE_CHECKING:
    from app.application.application import Application
    from app.domain.session import SessionId

logger = get_logger("Application->TrackingService")


@final
class TrackingService:
    """
    Orchestrates multi-object tracking operations and worker lifecycle.

    Responsibilities:
        - Start background ``TrackingWorker`` for multi-frame tracking.
        - Validate tracking prerequisites (layer data, worker view_state).
        - Clear tracking output layers before starting new tracking.
        - Synchronize tracking results from worker to ``DataLayer.C``.
        - Handle worker creation and view_state management.

    Note:
        Creates ``TrackingWorker`` instances (runs in background thread).
        Manages Layer C/D lifecycle (clears C before tracking, syncs after).
        Validates source layer (A or B detection data required).
        Does NOT manage tracking layer editing (delegates to ``TrackingLayerService``).

        Tracking Layers:
            ``DataLayer.C`` — Raw tracking output (immutable, machine-written).
            ``DataLayer.D`` — User-editable tracking results (seeded from C).
    """

    def __init__(self, app: Application):
        # self._app = app
        self._app_adapter = ApplicationAdapter(app)
        self._worker_manager = TrackingWorkerManager(
            app_adapter=self._app_adapter,
            worker_factory=TrackingWorkerFactoryAdapter(),
        )
        self._result_processor = TrackingResultProcessor(self._app_adapter)

    def start_background_tracking(
            self, s_id: SessionId, strategy_name: str, source_layer_name: VideoDataLayer
    ) -> None:
        """
        Start background multi-object tracking on detection/tracking data.
    
        Args:
            s_id (SessionId): Session ID.
            strategy_name (str): Tracking algorithm (e.g., "Hungarian", "DeepSort").
            source_layer_name (str): Source layer (``DataLayer.A`` or ``DataLayer.B``).
    
        Note:
            Flow:
                start_background_tracking(s_id, strategy, source_layer)
                  ├── Validate session ID is valid
                  ├── Check no tracking already running
                  ├── Validate source layer (A or B only)
                  ├── Validate source layer has detections
                  ├── Clear Layer C/D (immutable/editable tracking layers)
                  ├── Create TrackingWorker with source data
                  └──> Start worker in background thread
    
            Error Handling:
                Raises ``InvalidSessionIdException`` if session ID is invalid.
                Raises ``TrackingWorkerAlreadyRunningException`` if tracking already running.
                Raises ``UnsupportedLayerException`` if source layer is C or D (immutable).
                Raises ``EmptyLayerException`` if source layer has no detections.
    
            Side Effects:
                Clears ``DataLayer.C`` and ``DataLayer.D`` to prepare for new tracking.
                Creates and starts ``TrackingWorker`` thread.
        """
        logger.info("Starting background tracking for session: '{}' (strategy='{}', source='{}')",
                    s_id,
                    strategy_name,
                    source_layer_name)
        if not s_id:
            raise InvalidSessionIdException(
                message="Error while attempting to start tracking.", session_id=s_id
            )
        session = self._app_adapter.get_session_by_id(s_id)

        if not session.has_boxes_for_layer(source_layer_name):
            raise EmptyLayerException(
                message="Error while attempting to start tracking.",
                layer_name=source_layer_name,
                session_id=s_id,
            )

        self._worker_manager.start(s_id, strategy_name, source_layer_name)

        logger.info(
            "Tracking started for session '{}' (strategy={}, source={})",
            s_id,
            strategy_name,
            source_layer_name,
        )

    def sync_tracking_cache(self, s_id: SessionId) -> None:
        """
        Synchronize tracking results from worker to ``DataLayer.C`` (immutable tracking output).
    
        Args:
            s_id (SessionId): Session ID.
    
        Note:
            Called after ``TrackingWorker`` finishes processing all frames.
            Fetches tracking results from worker (dict of frame_index → [boxes]).
            Overwrites ``DataLayer.C`` with raw tracking output.
            ``DataLayer.D`` is seeded lazily (Just-In-Time) when accessed.
    
            Layer Updates:
                Layer.C — Updated with raw tracking worker output (immutable).
                Layer.D — NOT updated directly; seeded on-demand when user views tracking tab.
    
            Error Handling:
                Raises ``InvalidSessionIdException`` if session ID invalid.
                Raises ``TrackingWorkerNotFoundException`` if no worker exists for session.
    
            Side Effects:
                Overwrites all of ``DataLayer.C`` with new tracking data.
                Does NOT modify ``DataLayer.D`` (user keeps their edits unless user resets).
        """
        # ====================================================================
        # 1. VALIDATE SESSION ID
        # ====================================================================
        if not s_id:
            raise InvalidSessionIdException(
                message="Error while attempting to sync tracking cache.",
                session_id=s_id,
            )

        tracked_data = self._worker_manager.get_tracked_data(s_id)
        self._result_processor.overwrite_layer_c(s_id, tracked_data)

        # [AUDIT] DEAD CODE: 6 lines of commented JIT seeding and layer pruning logic
        # This appears to be deferred functionality for filtering Layer D by confidence.
        # Recommendation: Either implement or create a GitHub issue to track this feature request.
        # Leaving it commented creates ambiguity about whether it's intended or obsolete.
        # The comment "The JIT seeder has to filter out boxes" suggests this was planned.
        #
        # ======================================================
        # 3. Prune Layer D
        # ======================================================
        # session.data.purge_boxes_in_layer_by_minimum_confidence(
        #     DataLayer.D, session.view_state.settings.min_tracker_confidence
        # )

        logger.info(
            "Tracking cache synced for session '{}'. Layer C frames: {}",
            s_id,
            len(tracked_data),
        )
