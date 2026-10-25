"""
Tracking worker orchestration and multi-object tracking management.

See Also:
    - [`TrackingWorkerManager`][app.application.managers.tracking_worker.TrackingWorkerManager] — coordinates worker lifecycle
    - [`TrackingWorkerFactoryAdapter`][app.application.adapters.tracking_worker_factory_adapter.TrackingWorkerFactoryAdapter] — creates tracking workers

Layer: Application.
Context: Coordinates domain state and infrastructure to complete application use cases.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from app.application.adapters import (
    ApplicationAdapter,
    TrackingWorkerFactoryAdapter,
)
from app.application.managers.tracking_worker import TrackingWorkerManager
from app.application.services.tracking.result_processor import TrackingResultProcessor

from app.domain import VideoDataLayer
from app.shared import get_logger
from app.shared.exceptions import (
    InvalidSessionIdException,
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
        - Start background `TrackingWorker` for multi-frame tracking.
        - Validate tracking prerequisites (layer data, worker view_state).
        - Clear tracking output layers before starting new tracking.
        - Synchronize tracking results from worker to `DataLayer.C`.
        - Handle worker creation and view_state management.

    Note:
        Creates `TrackingWorker` instances (runs in background thread).
        Manages Layer C/D lifecycle (clears C before tracking, syncs after).
        Validates the source layer and seeds missing Layer B frames from Layer A.
        Does NOT manage tracking layer editing (delegates to `TrackingLayerService`).

        Tracking Layers:
            `DataLayer.C` — Post-processed tracking output (immutable, machine-written).
            `DataLayer.D` — User-editable tracking results (eagerly seeded from C).



    Args:
        app: Application adapted for tracking-worker startup and result processing against session data.
    """

    def __init__(self, app: Application):
        # self._app = app
        self._app_adapter = ApplicationAdapter(app)
        self._worker_manager = TrackingWorkerManager(
            app_adapter=self._app_adapter,
            worker_factory=TrackingWorkerFactoryAdapter(),
        )
        self._result_processor = TrackingResultProcessor(self._app_adapter)

    def get_detection_frame_coverage(self, s_id: SessionId) -> tuple[int, int]:
        """Return detection-frame coverage and total video frames before tracking.

        Args:
            s_id: Session to inspect without changing its annotation layers.

        Returns:
            Pair of initialized Layer A frame count and video frame count.
            Empty detection results count as processed; absent frames do not.
            Older/imported data can only provide evidence from stored entries,
            not proof that a particular background worker completed.
        """
        session = self._app_adapter.get_session_by_id(s_id)
        total = session.state.metadata.frame_count
        with session.data.data_lock:
            frames = session.data.get_all_boxes_for_layer_as_dict_of_lists(VideoDataLayer.A)
            processed = sum(0 <= frame_index < total for frame_index in frames)
        return processed, total

    def start_background_tracking(
            self, s_id: SessionId, strategy_name: str, source_layer_name: VideoDataLayer
    ) -> None:
        """
        Start background multi-object tracking on detection/tracking data.

        Args:
            s_id (SessionId): Session ID.
            strategy_name (str): Tracking algorithm (e.g., "Hungarian", "DeepSort").
            source_layer_name (str): Source layer (`DataLayer.A` or `DataLayer.B`).

        Note:
            Flow:
                start_background_tracking(s_id, strategy, source_layer)
                  ├── Validate session ID is valid
                  ├── Check no tracking already running
                  ├── Validate source layer (A or B only), seeding missing B frames
                  ├── Clear Layer C/D (immutable/editable tracking layers)
                  ├── Create TrackingWorker with source data
                  └──> Start worker in background thread

            Error Handling:
                Raises `InvalidSessionIdException` if session ID is invalid.
                Raises `TrackingWorkerAlreadyRunningException` if tracking already running.
                Raises `UnsupportedLayerException` if source layer is C or D (immutable).
                Raises `EmptyLayerException` if source layer has no detections.

            Side Effects:
                Clears `DataLayer.C` and `DataLayer.D` to prepare for new tracking.
                Creates and starts `TrackingWorker` thread.
        """
        logger.info("Starting background tracking for session: '{}' (strategy='{}', source='{}')",
                    s_id,
                    strategy_name,
                    source_layer_name)
        if not s_id:
            raise InvalidSessionIdException(
                message="Error while attempting to start tracking.", session_id=s_id
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
        Synchronize tracking results from worker to `DataLayer.C` (immutable tracking output).

        Args:
            s_id (SessionId): Session ID.

        Note:
            Called after `TrackingWorker` finishes processing all frames.
            Fetches tracking results from worker (dict of frame_index → [boxes]).
            Overwrites `DataLayer.C` with post-processed tracking output.
            Uninitialized `DataLayer.D` frames are eagerly seeded with the current filter.

            Layer Updates:
                Layer.C — Updated with post-processed tracking output (immutable).
                Layer.D — Seeded for uninitialized frames while preserving existing edits.

            Error Handling:
                Raises `InvalidSessionIdException` if session ID invalid.
                Raises `TrackingWorkerNotFoundException` if no worker exists for session.

            Side Effects:
                Overwrites all of `DataLayer.C` with new tracking data.
                Preserves initialized `DataLayer.D` frames (including user edits).
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

        logger.info(
            "Tracking cache synced for session '{}'. Layer C frames: {}",
            s_id,
            len(tracked_data),
        )
