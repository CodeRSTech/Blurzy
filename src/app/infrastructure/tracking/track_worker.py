"""Frame-aware background tracking worker and strategy dispatch."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import copy
from typing import Protocol

from PySide6.QtCore import QMutex, QMutexLocker, QThread, Signal

from app.infrastructure.tracking.bytetrack_strategy import ByteTrackStrategy
from app.infrastructure.tracking.box_deduplication import suppress_nested_same_class_boxes
from app.infrastructure.tracking.deepsort_strategy import DeepSortStrategy
from app.infrastructure.tracking.botsort_strategy import BotSortStrategy
from app.infrastructure.tracking.tracking_strategy import HungarianStrategy, DummyTracker
from app.infrastructure.tracking.post_processor import TrackingPostProcessor
from app.infrastructure.tracking.reid_extractor import PartBasedAppearanceEmbedder
from app.infrastructure.video.reader import VideoReader
from app.shared.logging_cfg import get_logger
if TYPE_CHECKING:
    from collections.abc import Sequence
    import numpy as np
    from PySide6.QtCore import QObject
    from app.domain.base.dtypes import ListOfBoxesByFrameIndexAsDict
    from app.domain.session import SessionState
    from app.domain.views import BBoxViewModel
    from app.infrastructure.dtypes import RGBFrame

logger = get_logger("Infrastructure->Tracking Worker")

class TrackerStrategy(Protocol):
    """Incremental strategy contract shared by frame-based trackers.

    Note:
        Strategies may ignore frame pixels and appearance features, but must
        accept them to keep worker dispatch independent of the selected tracker.
    """

    uses_appearance: bool

    def update_frame(
        self,
        frame_idx: int,
        frame_boxes: list[BBoxViewModel],
        frame: RGBFrame | None = None,
        embeddings: Sequence[np.ndarray | None] | None = None,
    ) -> list[BBoxViewModel]: ...


_STRATEGY_MAP: dict[str, type] = {
    "dummy": DummyTracker,
    "hungarian": HungarianStrategy,
    "bytetrack": ByteTrackStrategy,
    "deepsort": DeepSortStrategy,
    "botsort": BotSortStrategy,
}


class TrackingWorker(QThread):
    """
    Background QThread that runs multi-object tracking on frame detections.

    Strategy behavior in simple words:
        - ``dummy``: copy detections without real tracking.
        - ``hungarian``: match by box overlap (IoU), coast internally, and emit observed boxes only.
        - ``bytetrack``: prioritize strong matches and use weaker detections to keep IDs stable.
        - ``deepsort``: match using motion cascade, overlap, and appearance memory.
        - ``botsort``: combine direct width/height Kalman filtering with two-stage
          confidence matching and isolated Re-ID appearance updates.

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
        """Prepare a strategy worker with a stable detection snapshot.

        Args:
            strategy_name: Registered tracker strategy key.
            source_data: Per-frame detection boxes.
            session_state: Settings and video metadata for this run.
            parent: Optional Qt object parent.
            start: Whether to begin processing immediately.
        Raises:
            ModuleNotFoundError: If an optional selected tracker dependency is missing.
            ValueError: If a post-processing setting is outside its supported range.

        Note:
            Detection boxes are deep-copied and nested same-class duplicates are
            suppressed before worker-thread association begins.

        Example:
            worker = TrackingWorker("hungarian", detections, state)
        """
        super().__init__(parent)
        self._strategy_name = strategy_name
        self._session_state = session_state
        self._source_data = copy.deepcopy(source_data)
        self._source_data = {
            frame_index: suppress_nested_same_class_boxes(boxes)
            for frame_index, boxes in self._source_data.items()
        }
        self._processing_settings = copy.deepcopy(session_state.settings)

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
                min_detection_confidence=session_state.settings.min_detection_confidence,
                confidence_decay=session_state.settings.confidence_decay,
            )
        elif strategy_cls is DeepSortStrategy:
            self._tracker = DeepSortStrategy(
                min_iou=session_state.settings.min_iou,
                min_confidence=session_state.settings.min_tracker_confidence,
                confidence_decay=session_state.settings.confidence_decay,
            )
        elif strategy_cls is BotSortStrategy:
            self._tracker = BotSortStrategy(
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
                1. Open a thread-owned ``VideoReader`` when the session path exists.
                2. Read each frame, extract aligned embeddings, and call
                   ``_tracker.update_frame(...)``.
                3. Run appearance-aware offline stitching and coast generation.
                4. Store the result in ``_tracked_data`` under the mutex.
                5. Emit ``error_occurred(msg)`` on exceptions and always emit
                   ``finished_processing()``.
        Raises:
            None: Worker failures are signaled through ``error_occurred``.

        Note:
            Optional post-processing settings control tracklet stitching, GSI, and
            confidence-decayed coast tails after strategy tracking completes.

        Example:
            worker.start()
        """
        logger.debug("TrackingWorker QThread loop starting...")
        reader: VideoReader | None = None
        try:
            video_path = self._session_state.s_id.path
            embedding_dim = self._session_state.settings.reid_embedding_dim
            embedder = PartBasedAppearanceEmbedder(embedding_dim=embedding_dim)
            if isinstance(video_path, str) and video_path and os.path.isfile(video_path):
                reader = VideoReader(video_path)
            else:
                logger.debug(
                    "Tracking has no readable local video path; frame-aware features are disabled for path={!r}",
                    video_path,
                )

            result: ListOfBoxesByFrameIndexAsDict = {}
            appearance_embeddings_by_frame: dict[int, dict[str, np.ndarray]] = {}
            for frame_idx in range(self._total_frames):
                if self._stop_requested:
                    logger.debug("TrackingWorker stopped at frame {}", frame_idx)
                    return

                frame: RGBFrame | None = None
                if reader is not None and frame_idx < reader.frame_count:
                    actual_index, next_frame = reader.read_next_frame()
                    if actual_index != frame_idx:
                        next_frame = reader.read_frame_at_index(frame_idx)
                    frame = next_frame

                frame_boxes = self._source_data.get(frame_idx, [])
                embeddings = embedder.extract_for_boxes(frame, frame_boxes)
                frame_result = self._tracker.update_frame(
                    frame_idx,
                    frame_boxes,
                    frame=frame,
                    embeddings=embeddings,
                )
                result[frame_idx] = frame_result
                isolated = self._isolated_detection_indices(frame_boxes)
                frame_appearance: dict[str, np.ndarray] = {}
                for tracked_box in frame_result:
                    if not tracked_box.detection_backed or tracked_box.time_since_update != 0:
                        continue
                    best_index = self._best_detection_index(tracked_box, frame_boxes)
                    if best_index is None or best_index not in isolated:
                        continue
                    embedding = embeddings[best_index]
                    if embedding is not None:
                        frame_appearance[tracked_box.id] = embedding.copy()
                if frame_appearance:
                    appearance_embeddings_by_frame[frame_idx] = frame_appearance
                self.progress_updated.emit(frame_idx + 1, self._total_frames)

            if self._stop_requested:
                return

            settings = self._processing_settings
            metadata = self._session_state.metadata
            metadata_fps = metadata.fps
            fps = metadata_fps if isinstance(metadata_fps, (int, float)) and metadata_fps > 0 else 30.0
            metadata_width = metadata.width
            frame_width = metadata_width if isinstance(metadata_width, int) and metadata_width > 0 else 0
            metadata_height = metadata.height
            frame_height = metadata_height if isinstance(metadata_height, int) and metadata_height > 0 else 0
            result = TrackingPostProcessor(
                max_gap=settings.max_stitch_gap,
                gsi_smoothness=settings.gsi_smoothness,
                confidence_decay=settings.confidence_decay,
                min_confidence=settings.min_tracker_confidence,
                offline_stitching_enabled=settings.offline_stitching_enabled,
                privacy_features_enabled=settings.privacy_features_enabled,
                resist_box_shrinking=settings.resist_box_shrinking,
                shrink_resistance=settings.shrink_resistance,
                pre_detection_padding_sec=settings.pre_detection_padding_sec,
                post_detection_padding_sec=settings.post_detection_padding_sec,
                box_safety_padding_pct=settings.box_safety_padding_pct,
                fps=fps,
                frame_width=frame_width,
                frame_height=frame_height,
            ).process(
                result,
                total_frames=self._total_frames,
                appearance_embeddings_by_frame=appearance_embeddings_by_frame,
            )

            with QMutexLocker(self._mutex):
                self._tracked_data = result

            self.progress_updated.emit(len(result), len(result))
            self._is_complete = True
            logger.info("TrackingWorker completed successfully. Processed frames output: {}", len(result))
        except Exception as exc:
            logger.opt(exception=True).exception("TrackingWorker failed")
            self.error_occurred.emit(str(exc))
        finally:
            if reader is not None:
                reader.close()
            self.finished_processing.emit()

    @staticmethod
    def _isolated_detection_indices(frame_boxes: list[BBoxViewModel]) -> set[int]:
        """Return boxes whose IoU with every other same-frame box is below 0.25."""
        isolated: set[int] = set()
        for index, box in enumerate(frame_boxes):
            if all(
                TrackingWorker._iou(box.bbox_xyxy, other.bbox_xyxy) < 0.25
                for other_index, other in enumerate(frame_boxes)
                if other_index != index
            ):
                isolated.add(index)
        return isolated

    @staticmethod
    def _best_detection_index(
        tracked_box: BBoxViewModel,
        frame_boxes: list[BBoxViewModel],
    ) -> int | None:
        """Find the input detection matching a detection-backed tracker output."""
        candidates = [
            (index, TrackingWorker._iou(tracked_box.bbox_xyxy, box.bbox_xyxy))
            for index, box in enumerate(frame_boxes)
            if box.label == tracked_box.label
        ]
        if not candidates:
            return None
        index, overlap = max(candidates, key=lambda item: item[1])
        return index if overlap >= 0.5 else None

    @staticmethod
    def _iou(
        first: tuple[int, int, int, int],
        second: tuple[int, int, int, int],
    ) -> float:
        """Return box intersection-over-union for two xyxy rectangles."""
        x1 = max(first[0], second[0])
        y1 = max(first[1], second[1])
        x2 = min(first[2], second[2])
        y2 = min(first[3], second[3])
        intersection = max(0, x2 - x1) * max(0, y2 - y1)
        area_a = max(0, first[2] - first[0]) * max(0, first[3] - first[1])
        area_b = max(0, second[2] - second[0]) * max(0, second[3] - second[1])
        union = area_a + area_b - intersection
        return intersection / union if union > 0 else 0.0
