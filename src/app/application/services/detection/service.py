"""Detection service orchestration for model-based object detection across sessions."""

from __future__ import annotations

from typing import final, override, TYPE_CHECKING

from PySide6.QtCore import Slot

from app.application.adapters import ApplicationAdapter
from app.application.adapters.detection_worker_factory_adapter import DetectionWorkerFactoryAdapter
from app.application.managers.detection_engine import DetectionEngineManager
from app.application.services.detection.batch_processor import DetectionBatchProcessor
from app.application.services.detection.execution_service import DetectionExecutionService
from app.domain import DetectionResult, SessionId
from app.shared.exceptions import WorkerAlreadyRunningException, NullModelNameException
from app.shared.logging_cfg import get_logger

logger = get_logger("Application->DetectionService")

if TYPE_CHECKING:
    from app.application.application import Application


@final
class DetectionService:
    """
    Orchestrates object detection operations and detection engine management.

    Responsibilities:
        - Create and manage ``DetectionEngine`` instances (one per session, per model).
        - Execute single-frame detection via ``detect_current_frame()``.
        - Start background detection workers for processing entire sessions.
        - Apply confidence and label filtering to detection results.
        - Store detection results in session data layer.
        - Handle model switching and clearing detection layers.

    Note:
        Does not directly create DetectionWorker (delegates to external code).
        Manages DetectionEngine lifecycle (creation, model updates).
        Filters raw YOLO detections by confidence and chosen labels.
        Stores filtered results in ``DataLayer.B`` (detection layer).

        ``detect_current_frame()`` — Single-frame detection (blocking, for UI immediate use).
        ``create_or_update_detection_engine_from_model_name_for_session_id()`` — Model management.
        ``start_detection_worker_for_session_id()`` — Background detection (threading).
    """

    def __init__(self, app: Application) -> None:
        # [AUDIT] TESTABILITY & SRP ISSUE: Services created inline without factory abstraction
        # Each service below creates its own dependencies, making mocking and testing difficult.
        # Recommendation: Use a Dependency Injection Container or Factory to compose services:
        #   detectionServiceFactory = DetectionServiceFactory(app)
        #   service = detectionServiceFactory.create_detection_service()
        # This improves:
        #   - Testability (mock entire dependency graph once)
        #   - Flexibility (swap implementations via container)
        #   - Separation of concerns (composition logic isolated)
        self._app_adapter = ApplicationAdapter(app)
        self._batch_processor = DetectionBatchProcessor(self._app_adapter)
        self._engine_manager = DetectionEngineManager(self._app_adapter)
        self._execution_service = DetectionExecutionService(self._app_adapter, self._engine_manager)
        self._worker_factory = DetectionWorkerFactoryAdapter()

    @override
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"

    def detect_current_frame_and_populate_layer_b_at_current_index(self, s_id: SessionId) -> None:
        # [AUDIT] METHOD NAMING: Name is 69 characters, exceeds Zen of Python readability
        # `detect_current_frame_and_populate_layer_b_at_current_index` is too verbose.
        # This wraps across most terminal widths (standard 80 chars) reducing readability.
        # Recommendation: Shorten to `detect_current_frame()` and document details in docstring:
        # - Callers already know it's the "current" frame (from context)
        # - Layer/index details are implementation details suitable for docstring
        # Benefits: Improves readability, easier to read call sites
        """
        Run the existing single-frame detection flow via the execution collaborator.

        The ``...layer_b...`` name is a backward-compatible legacy API surface.
        Despite that name, this method populates Layer A, matching the prior
        runtime behavior; Layer B remains seeded lazily elsewhere.
        """
        self._execution_service.execute_for_current_frame(s_id)

    def set_detection_model_for_session_id(
            self, s_id: SessionId, model_name: str, keep_manual: bool = False
    ) -> None:
        """
        Sets the detection model for a given session and updates its settings.
        """
        session = self._app_adapter.get_session_by_id(s_id)

        if session.detection_worker is None:
            logger.info("No existing detection worker found for session '{}'", s_id)
        else:
            logger.info("Stopping existing detection worker for session '{}'", s_id)
            session.detection_worker.stop()
            session.detection_worker = None

        session.reset_model(model_name, keep_manual)

        if model_name == "None":
            logger.info("Deleting detection engine and session layers for Session: '{}'", s_id)
            self._engine_manager.remove(s_id)
            return

        self._create_or_update_detection_engine_from_model_name_for_session_id(model_name, s_id)

        logger.info("Detection model set for session '{}'. Layers cleared.", s_id)

    def start_detection_worker_for_session_id(self, s_id: SessionId) -> None:
        """
        Starts a background ``DetectionWorker`` .
        """
        logger.info("Starting background detection (DetectionWorker) for session '{}'", s_id)
        session = self._app_adapter.get_session_by_id(s_id)

        # Confirm that worker is either absent or not running
        if session.has_running_detection_worker:
            logger.warning(
                "Rejected detection start for session '{}': detection worker is already running",
                s_id,
            )
            raise WorkerAlreadyRunningException(
                message="Error while attempting to start detection via DetectionService", session_id=s_id
            )

        # Confirm that model name isn't empty or None
        if session.state.settings.model_name_is_null:
            logger.warning(
                "Rejected detection start for session '{}': no detection model is configured",
                s_id,
            )
            raise NullModelNameException(
                message="Select a detection model before starting background detection.", session_id=s_id
            )

        # ============================================================================
        # Clear all layers for the session (to ensure that we get a clean start)
        # ============================================================================
        session.data.clear_all_layers()

        # ============================================================================
        # Initialize Detection Engine
        # ============================================================================
        self._create_or_update_detection_engine_from_model_name_for_session_id(
            model_name=session.state.settings.detection_model_name, s_id=s_id
        )
        # ============================================================================
        # Create Detection Worker, connect signals and start it.
        # ============================================================================
        if session.detection_engine is None:
            raise RuntimeError(
                f"Detection engine is None for session '{s_id}' after attempting to create it. This should never happen."
            )
        detection_worker = self._worker_factory.create(session.s_id, session.detection_engine)
        detection_worker.batch_ready.connect(self.on_detection_batch_ready)
        detection_worker.progress_updated.connect(self.on_detection_progress_updated)
        detection_worker.start()

        session.detection_worker = detection_worker

    @Slot(object, object, float)
    def on_detection_batch_ready(self, s_id: SessionId, batch: dict[int, list[DetectionResult]],
                                 batch_processing_time: float) -> None:
        """
        Runs on the Main Thread safely.
        Receives batches of detections from the worker and pushes them into the Domain Session.
        """
        try:
            report = self._batch_processor.process_batch(s_id, batch)
        except KeyError:
            # Failsafe: Worker pushed data but session was just closed by the user
            return

        logger.trace(
            "Synced batch of {} frames. Session: '{}' time: {} ms (written={} skipped={} boxes={})",
            report.total_frames,
            s_id,
            batch_processing_time,
            report.written_frames,
            report.skipped_existing_frames,
            report.written_boxes,
        )

    # Slot for detection worker progress update
    @Slot(int, int, float)
    def on_detection_progress_updated(self, processed_frames: int, total_frames: int, eta_msecs: float | None) -> None:
        if eta_msecs is not None:
            eta_seconds = int(eta_msecs // 1000)
            logger.trace("Detection worker processed {}/{} frames. ETA: {}s", processed_frames, total_frames,
                         eta_seconds + 1)
        else:
            logger.trace("Detection worker processed {}/{} frames.", processed_frames, total_frames)

    def _create_or_update_detection_engine_from_model_name_for_session_id(
            self, model_name: str, s_id: SessionId
    ) -> None:
        """
        Create or update the detection engine for a session with a new model.

        Args:
            model_name (str): Name of detection model to load (e.g., "yolov8n", "yolov11m").
            s_id (SessionId): Session ID identifying the target session.

        Note:

        - Delegates to ``DetectionEngineManager.create_or_update()``.
        - Kept for backward-compatibility as an internal helper; new code
        - should call the manager directly.
        """
        self._engine_manager.create_or_update(s_id, model_name)
