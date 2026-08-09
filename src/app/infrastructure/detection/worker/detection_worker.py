"""Background YOLO detection worker — thread-safe batch frame inference."""

from __future__ import annotations

import time
from typing import final, override

from PySide6.QtCore import QObject, QThread, QMutex, QMutexLocker, Signal

from app.application.interfaces import DetectionEngineInterface
from app.domain.detection.result import DetectionResult
from app.domain.session.session_id import SessionId
from app.infrastructure.video.reader import VideoReader
from app.shared.exceptions import EndOfVideoStreamException
from app.shared.logging_cfg import get_logger

logger = get_logger("Infrastructure->Detection->DetectionWorker")


@final
class DetectionWorker(QThread):
    """
    Background QThread that runs YOLO inference on all video frames, emitting batches asynchronously.

    Attributes:
        _s_id (SessionId): Session ID for batch routing.
        _video_path (str): Video path extracted from ``s_id``.
        _detection_engine (DetectionEngine): YOLO model wrapper used for inference.
        _detections_by_frame_index (dict[int, list[DetectionResult]]): Thread-safe cache
            protected by ``_mutex``.
        _mutex (QMutex): Guards base detection view_state.
        _stop_requested (bool): True when shutdown is requested.
        _is_complete (bool): True after the full stream is processed.

    Note:
        Signals emitted by this worker:
            progress_updated(frame_idx, total_frames): Emitted per frame for UI sync.
            batch_ready(s_id, batch): Emitted every 30 frames.
            finished_processing(): Emitted when the thread exits.
            error_occurred(msg): Emitted on exception.

        Thread lifecycle: ``start()`` triggers the native QThread lifecycle,
        ``run()`` loops and emits, ``stop()`` sets ``_stop_requested``, and
        ``finished_processing()`` is emitted when the thread exits.

        Batch emission: accumulate detections in ``current_batch`` until it reaches 30
        frames, emit ``batch_ready()``, then reset. Remaining frames are flushed at
        stream end.

        Thread affinity: do not access UI from ``run()``. Only emit signals.
        Callers must use ``moveToThread(worker)`` before starting.
        Shutdown sequence: ``worker.stop()`` -> ``worker.quit()`` -> ``worker.wait()``
        -> ``deleteLater()``.

    Example:
        worker = DetectionWorker(s_id, engine)
        thread = QThread()
        worker.moveToThread(thread)
        worker.batch_ready.connect(on_batch_ready)
        worker.finished_processing.connect(thread.quit)
        thread.start()
        worker.start()
    """
    # Added signals to match Qt paradigms while keeping your original methods intact
    progress_updated = Signal(int, int, float)  # current_frame, total_frames, eta_msecs
    finished_processing = Signal()
    error_occurred = Signal(str)

    # NEW: The thread-safe push callback
    batch_ready = Signal(object, object, float)  # s_id, dict[frame_index, list[DetectionResult]], batch_processing_time

    def __init__(
        self, s_id: SessionId, detection_engine: DetectionEngineInterface, parent: QObject | None = None
    ) -> None:
        """Initialize worker for ``s_id`` using the given ``detection_engine``."""
        super().__init__(parent)
        self._s_id = s_id  # Store the SessionId object
        self._video_path = s_id.path  # Extract path for the reader
        self._detection_engine = detection_engine
        # [AUDIT] SEPARATION OF CONCERNS: Worker mixes result caching with signal emission
        # _detections_by_frame_index stores inference results (data responsibility)
        # but batch_ready Signal emits these (event responsibility).
        # This conflates two concerns: persistence and event notification.
        # Recommendation: Extract result caching to a separate DetectionResultCache class.
        # Worker responsibility: run inference and emit batches
        # Cache responsibility: store and retrieve detection results
        # This improves testability and makes concerns explicit.
        self._detections_by_frame_index: dict[int, list[DetectionResult]] = {}

        self._mutex = QMutex()
        self._stop_requested = False
        self._is_complete = False

        logger.info("Initialized detection worker for video: {}", self._video_path)

    @override
    def start(self, priority: QThread.Priority = QThread.Priority.InheritPriority) -> None:
        """Start the detection thread (calls ``run()`` in background)."""
        logger.info("Starting detection worker for {}", self._video_path)

        # Check both our custom flag and the native QThread view_state
        if super().isRunning():
            logger.info("Detection worker is already running for {}", self._video_path)
            return

        self._stop_requested = False
        self._is_complete = False

        # Call the native QThread start to invoke run() in the background
        super().start(priority)
        logger.info("Detection worker started for {}", self._video_path)

    def stop(self) -> None:
        """Request thread to stop (sets ``_stop_requested`` flag)."""
        self._stop_requested = True
        logger.info("Detection worker stop requested for {}", self._video_path)

    def isRunning(self) -> bool:
        """Return True if thread is currently processing frames."""
        logger.trace("Detection worker isRunning() called")
        return super().isRunning()

    def is_complete(self) -> bool:
        """Return True if stream reached end (all frames processed)."""
        logger.trace("Detection worker is_complete() called")
        return self._is_complete

    def get_detections(self, frame_index: int) -> list[DetectionResult] | None:
        """Retrieve cached detections for ``frame_index``, or None if not yet processed."""
        logger.trace("Detection worker get_detections() called for frame {}", frame_index)
        with QMutexLocker(self._mutex):
            detections = self._detections_by_frame_index.get(frame_index)
            if detections is None:
                return None
            return list(detections)

    def get_all_detections(self) -> dict[int, list[DetectionResult]]:
        """Return copy of all cached detections (thread-safe via ``_mutex``)."""
        logger.trace("Detection worker get_all_detections() called")
        with QMutexLocker(self._mutex):
            return {
                frame_index: list(detections)
                for frame_index, detections in self._detections_by_frame_index.items()
            }

    @override
    def run(self) -> None:
        """
        Main thread loop — read all frames, run YOLO inference, emit batches (30 frames).

        Note:
            Workflow:
                1. Open ``VideoReader`` for ``_video_path``.
                2. Loop: read frame, call ``_detection_engine.detect()``, and store the
                   result in the cache and current batch.
                3. Every 30 frames, emit ``batch_ready(s_id, batch)`` and reset the batch.
                4. On stream end, flush any remaining batch.
                5. On exception, emit ``error_occurred(msg)``.
                6. Finally, close the reader and emit ``finished_processing()``.

            Do not access UI from this thread. Only emit signals.
            ``progress_updated()`` is used to synchronize UI progress.
        """
        logger.trace("Detection worker thread running for {}", self._video_path)
        reader = VideoReader(self._video_path)

        batch_size = 30
        current_batch: dict[int, list[DetectionResult]] = {}

        try:
            total_frames = reader.frame_count
            batch_processing_start_time = time.time()
            frame_processing_start_time = time.time()
            logger.info("Detection worker starting for {}", self._video_path)

            while not self._stop_requested:
                try:
                    actual_index, frame = reader.read_next_frame()
                except EndOfVideoStreamException:
                    logger.info("Reached end of video stream for {}, stopping", self._video_path)
                    self._is_complete = True
                    self.stop()
                    break

                # Run ML model
                detections = self._detection_engine.detect(frame)

                # 1. Add to the worker's internal cache
                with QMutexLocker(self._mutex):
                    self._detections_by_frame_index[actual_index] = detections

                # 2. Add to our current batch
                current_batch[actual_index] = detections

                # 3. If the batch hits 30 frames, push it across the thread boundary!
                if len(current_batch) >= batch_size:
                    batch_processing_time = time.time() - batch_processing_start_time
                    self.batch_ready.emit(self._s_id, current_batch, batch_processing_time)
                    current_batch = {}  # Reset the batch

                # Emit progress for UI synchronization
                eta_msecs = ((time.time() - frame_processing_start_time)
                             / (actual_index + 1) * (total_frames - actual_index - 1)
                             * 1000) if total_frames > 0 else None
                self.progress_updated.emit(
                    actual_index + 1,
                    total_frames if total_frames > 0 else actual_index + 1,
                    eta_msecs
                )

            # Flush any remaining frames in the batch when stopped/finished
            if current_batch:
                batch_processing_time = time.time() - batch_processing_start_time
                self.batch_ready.emit(self._s_id, current_batch, batch_processing_time)

            if self._is_complete:
                logger.info("Detection worker completed for {}", self._video_path)
            else:
                logger.info("Detection worker stopped early for {}", self._video_path)

        except Exception as e:
            logger.opt(exception=True).exception("Detection worker failed for {}", self._video_path)
            self.error_occurred.emit(str(e))

        finally:
            reader.close()
            self.finished_processing.emit()
