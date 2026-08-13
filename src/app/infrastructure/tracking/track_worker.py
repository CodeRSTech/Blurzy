"""Background tracking worker with strategy pattern (Dummy/Hungarian/ByteTrack/DeepSORT)."""

from __future__ import annotations

from typing import TYPE_CHECKING


import copy
from typing import Protocol, TYPE_CHECKING

from PySide6.QtCore import QMutex, QMutexLocker, QThread, Signal

from app.infrastructure.tracking.bytetrack_strategy import ByteTrackStrategy
from app.infrastructure.tracking.deepsort_strategy import DeepSortStrategy
from app.infrastructure.tracking.tracking_strategy import HungarianStrategy, DummyTracker
from app.shared.logging_cfg import get_logger
if TYPE_CHECKING:
    from PySide6.QtCore import QObject


if TYPE_CHECKING:
    from app.domain.base.dtypes import ListOfBoxesByFrameIndexAsDict
    from app.domain.session import SessionState

logger = get_logger("Infrastructure->Tracking Worker")

class TrackerStrategy(Protocol):
    """Protocol (structural type) for tracker implementations."""
    def track(
            self,
            source_data: ListOfBoxesByFrameIndexAsDict,
            total_frames: int = 0,
    ) -> ListOfBoxesByFrameIndexAsDict: ...


_STRATEGY_MAP: dict[str, type] = {
    "dummy": DummyTracker,
    "hungarian": HungarianStrategy,
    "bytetrack": ByteTrackStrategy,
    "deepsort": DeepSortStrategy,
}


class TrackingWorker(QThread):
    """
    Background QThread that runs multi-object tracking on frame detections.

    Strategy behavior in simple words:
        - ``dummy``: copy detections without real tracking.
        - ``hungarian``: match by box overlap (IoU) and coast tracks with decay.
        - ``bytetrack``: prioritize strong matches and use weaker detections to keep IDs stable.
        - ``deepsort``: match using movement + overlap + appearance features.

    Attributes:
        _strategy_name (str): Tracking strategy name, such as ``"dummy"`` or
            ``"hungarian"``.
        _source_data (BoxesByFrameIndex): Deep copy of the input detections.
        _tracked_data (BoxesByFrameIndex): Output tracking results protected by
            ``_mutex``.
        _mutex (QMutex): Guards tracked output view_state.
        _stop_requested (bool): True when early stop is requested.
        _is_complete (bool): True after tracking finishes successfully.
        _tracker (TrackerStrategy): Tracking strategy instance.

    Note:
        Signals emitted by this worker:
            progress_updated(frame_count, frame_count): Final processed frame count.
            finished_processing(): Emitted when the thread exits.
            error_occurred(msg): Emitted if tracking raises an exception.

    Example:
        settings = ProcessingSettings(min_iou=0.3, confidence_decay=0.05, ...)
        worker = TrackingWorker("hungarian", source_boxes, settings, start=True)
        results = worker.get_tracked_data()
    """
    progress_updated = Signal(int, int)
    finished_processing = Signal()
    error_occurred = Signal(str)

    def __init__(self, strategy_name: str, source_data: ListOfBoxesByFrameIndexAsDict, session_state: SessionState,
                 parent: QObject | None = None, start: bool = False) -> None:
        super().__init__(parent)
        self._strategy_name = strategy_name
        # [AUDIT] CLARITY: Deep copy without explanation of memory implications
        # Deep copying large detection dictionaries (frame_index → list[boxes]) can be expensive.
        # WHY deep copy? To isolate tracking worker from concurrent modifications to the source layer
        # while tracking runs in background. This prevents race conditions and data inconsistency.
        # PERFORMANCE NOTE: If source_data is large (e.g., 1000+ frames with many detections),
        # this may introduce noticeable latency. Consider adding a configuration option for copy strategy.
        self._source_data = copy.deepcopy(source_data)

        # EXTRACT AND SAVE TOTAL FRAMES
        self._total_frames = session_state.metadata.frame_count

        self._tracked_data: ListOfBoxesByFrameIndexAsDict = {}
        self._mutex = QMutex()
        self._stop_requested = False
        self._is_complete = False

        strategy_cls = _STRATEGY_MAP.get(strategy_name, DummyTracker)

        # Pass tracker params only to strategies that accept them
        self._tracker: TrackerStrategy

        if strategy_cls is HungarianStrategy:
            self._tracker = HungarianStrategy(
                iou_threshold=session_state.settings.min_iou,
                confidence_decay=session_state.settings.confidence_decay,
                min_confidence=session_state.settings.min_tracker_confidence
            )
        elif strategy_cls is ByteTrackStrategy:
            self._tracker = ByteTrackStrategy(
                min_iou=session_state.settings.min_iou,
                min_confidence=session_state.settings.min_tracker_confidence,
            )
        elif strategy_cls is DeepSortStrategy:
            self._tracker = DeepSortStrategy(
                min_iou=session_state.settings.min_iou,
                min_confidence=session_state.settings.min_tracker_confidence,
                confidence_decay=session_state.settings.confidence_decay,
            )
        else:
            self._tracker = strategy_cls()

        logger.info(
            "TrackingWorker initialized: strategy='{}', frames={}, parent={}",
            strategy_name,
            len(source_data),
            parent,
        )
        if start:
            self.start()

    def __repr__(self):
        return f"<{self.__class__.__name__}(strategy={self._strategy_name}, frames={len(self._source_data)}, complete={self._is_complete})>"

    def stop(self) -> None:
        """Request early stop (reserved for future use)."""
        self._stop_requested = True

    def isRunning(self) -> bool:
        """Return True while the underlying QThread is active."""
        return super().isRunning()

    def is_complete(self) -> bool:
        """Return True if tracking finished successfully."""
        return self._is_complete

    def get_tracked_data(self) -> ListOfBoxesByFrameIndexAsDict:
        """Return deep copy of tracked results (thread-safe via ``_mutex``)."""
        with QMutexLocker(self._mutex):
            return copy.deepcopy(self._tracked_data)

    def run(self) -> None:
        """
        Main thread loop — run the tracking strategy on source data and store results.

        Note:
            Workflow:
                1. Call ``_tracker.track(source_data)``.
                2. If a stop is requested, return early.
                3. Store the result in ``_tracked_data`` under the mutex.
                4. Emit ``progress_updated(frame_count, frame_count)``.
                5. On exception, emit ``error_occurred(msg)``.
                6. Finally, emit ``finished_processing()``.
        """
        logger.debug("TrackingWorker QThread loop starting...")
        try:
            # PASS TOTAL FRAMES TO THE TRACKER
            result = self._tracker.track(self._source_data, total_frames=self._total_frames)

            if self._stop_requested:
                logger.debug("TrackingWorker stopped prematurely due to stop request")
                return

            with QMutexLocker(self._mutex):
                self._tracked_data = result

            self.progress_updated.emit(len(result), len(result))
            self._is_complete = True
            logger.info("TrackingWorker completed successfully. Processed frames output: {}", len(result))
        except Exception as exc:
            logger.opt(exception=True).exception("TrackingWorker failed")
            self.error_occurred.emit(str(exc))
        finally:
            self.finished_processing.emit()
