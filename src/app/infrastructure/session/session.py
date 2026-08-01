"""Session container managing state, workers, frame buffering, and layer CRUD operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from PySide6.QtCore import QObject

from app.application.interfaces import DetectionEngineInterface, DetectionWorkerInterface, \
    TrackingWorkerInterface
from app.domain import VideoDataLayer, SessionState
from app.infrastructure.dtypes import RGBFrame
from app.infrastructure.session.session_data_store import SessionDataStore
from app.infrastructure.video import VideoReader
from app.infrastructure.video.decode_worker import VideoDecodeWorker
from app.shared.logging_cfg import get_logger

if TYPE_CHECKING:
    from app.domain.session import SessionId
    from app.domain.base.dtypes import ListOfBoxesByFrameIndexAsDict, ListOfBoxes

logger = get_logger("Domain->Session")




@final
class Session(QObject):
    """
    Container holding all state and workers for a single video processing session.
    """

    def __init__(self, s_id: SessionId) -> None:
        # [AUDIT] SRP VIOLATION - God Object Antipattern
        # Session.__init__ has 5+ distinct responsibilities:
        # 1. Initialize video I/O (VideoReader)
        # 2. Create domain state (SessionState)
        # 3. Manage worker lifecycle (VideoDecodeWorker.start() — side effect!)
        # 4. Reference external components (detection_engine, workers — nulled here)
        # 5. Initialize data persistence (SessionDataStore)
        #
        # CONSEQUENCES:
        # - Hard to unit test (requires live video file, starts threads)
        # - Violates Single Responsibility Principle
        # - Tight coupling to Infrastructure classes (VideoReader, VideoDecodeWorker)
        #
        # RECOMMENDED FIX:
        # Use a Factory or Builder pattern:
        #   1. SessionFactory creates bare Session with only SessionState
        #   2. SessionInitializer separately configures workers
        #   3. Workers injected via dependency injection, not created in Session
        super().__init__()

        # ┌─ SESSION ID AND DATA STORE ──────────────────────────┐
        self.s_id = s_id
        self.data = SessionDataStore(s_id=self.s_id, parent=self)
        #
        # ├── VIDEO READER ──────────────────────────────────────────────────────────────────────────────┐
        # This particular `VideoReader` instance is used ONLY by the `DetectionService` 
        # to read the current frame
        #
        # Create a VideoReader instance. This will be:
        #   - used by the `DetectionService` to read a frame in its `detect_current_frame()` method.
        #   - used to extract metadata from the video file for initialization of the SessionState.
        self.video_reader = VideoReader(self.s_id.path)
        #
        # ├─ SESSION STATE ──────────────────────────────────────────────────────────────────────────────┐
        # Create a SessionState instance and set it as the state.
        #
        # Although we can skip passing metadata and let Session extract it from the reader,
        # Session isn't supposed to know about VideoReader,
        # since it lives within DOMAIN layer and,
        # `VideoReader` lives within INFRASTRUCTURE layer, where
        # Domain layer isn't supposed to know about Infrastructure layer but,
        # Infrastructure layer can know about Domain layer.
        #
        #   ( Session Manager, Handlers, ... )
        # --------- APPLICATION LAYER ----------
        #      |                        |
        #      |                        |
        #      v                        v
        # DOMAIN LAYER <-------- INFRASTRUCTURE LAYER
        # ( Session, ... )      ( VideoReader, ... )
        self.state = SessionState(self.s_id, self.video_reader.metadata)
        #
        # ├─ VIDEO DECODE WORKER ────────────────────────────────────────────────────────────────────────┐
        # Create a `VideoDecodeWorker` instance and start it.
        # [NOTE] Even though we start the worker here,
        # it will only be active and doing the decoding work when the session becomes active.
        self.video_decode_worker = VideoDecodeWorker(self.s_id.path, self.state.playback, parent=self)
        # [AUDIT] SIDE EFFECT IN __init__: Starting a thread during object construction
        # is unexpected and hard to reason about. __init__ should not have observable effects.
        # Recommendation: Move .start() to a separate initialization method or factory,
        # called explicitly by SessionManager after Session is fully constructed.
        self.video_decode_worker.start()
        #
        # ├─ DETECTION ENGINE, DETECTION WORKER AND TRACKING WORKER ─────────────────────────────────────┐
        #
        #   [NOTE]
        #       `DetectionWorker` COULD contain the `DetectionEngine`
        #       It has NOT been fully determined whether ought to be optimal
        #       OR even worth it.
        #       POINTS THAT SUPPORT `DetectionWorker` CONTAINING `DetectionEngine`
        #           - It's NOT the responsibility of the `Session` to instantiate/own the `DetectionEngine` BUT,
        #             it COULD be the responsibility of the SessionService
        #           - TrackingWorker OWNS it's Tracking Strategies
        #           - DetectionWorker (and the rest, if any)
        #             EXCLUSIVELY interact with
        #             the `DetectionEngine` via DetectionService
        self.detection_engine: DetectionEngineInterface | None = None
        self.detection_worker: DetectionWorkerInterface | None = None
        self.tracking_worker: TrackingWorkerInterface | None = None

    def __repr__(self):
        return f"<Session id={self.s_id.basename}>"

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #                           PROPERTIES
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    @property
    def has_buffered_frame(self) -> bool:
        """Check if the session has a buffered frame."""
        return self.get_buffered_frame() is not None

    @property
    def has_running_detection_worker(self) -> bool:
        return self.detection_worker is not None and self.detection_worker.isRunning()

    @property
    def has_running_tracking_worker(self) -> bool:
        return self.tracking_worker is not None and self.tracking_worker.isRunning()

    @property
    def is_at_last_frame(self) -> bool:
        """Check if the `current frame index` of ``playback`` state **>=**

        `frame count` of the video ``metadata``."""
        return self.state.is_at_last_frame

    @property
    def is_playing_video(self) -> bool:
        """Check if the session is currently playing the video."""
        return self.state.playback.is_playing

    @is_playing_video.setter
    def is_playing_video(self, is_playing: bool) -> None:
        self.state.playback.is_playing = is_playing

    def close(self) -> None:
        """Stop all workers (detection, tracking, decode) and close reader."""
        if self.detection_worker is not None:
            self.detection_worker.stop()
        if self.tracking_worker is not None:
            self.tracking_worker.stop()
        if self.video_decode_worker is not None:
            self.video_decode_worker.stop()

        self.video_reader.close()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #                            LAYER CRUD MANAGEMENT
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def get_layer_by_name(self, layer_name: VideoDataLayer) -> ListOfBoxesByFrameIndexAsDict:
        return self.data.get_all_boxes_for_layer_as_dict_of_lists(layer_name)

    def get_layer_boxes_for_index(self, layer_name: VideoDataLayer, frame_index: int) -> ListOfBoxes:
        # Natively fetches the list directly from the Pandas dataframe!
        return self.data.get_boxes_for_layer_at_frame_index_as_list(layer_name, frame_index)

    def get_layer_boxes_for_current_frame(self, layer_name: VideoDataLayer) -> ListOfBoxes:
        return self.get_layer_boxes_for_index(layer_name, self.state.playback.current_frame_index)

    def has_boxes_for_layer(self, layer_name: VideoDataLayer) -> bool:
        return self.data.has_boxes_for_layer(layer_name)

    def stop_playback(self):
        self.state.playback.stop_playback()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #                           FRAME CONTROLS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def get_buffered_frame(self) -> RGBFrame | None:
        """Get the next frame (current_idx + 1) from the ring buffer (for lookahead during playback)."""
        next_idx = self.state.playback.current_frame_index + 1
        return self.get_frame_by_index(next_idx)

    def get_frame_by_index(self, frame_index: int) -> RGBFrame | None:
        """
        Fetch frame at ``frame_index`` from the ring buffer cache with timeout-based seek handling.

        Note:
            Workflow:
                1. Clamp ``frame_index`` to the valid range.
                2. Check the ring buffer cache and return immediately on a hit.
                3. On a miss, either wait for sequential playback to catch up or trigger
                   ``request_seek()`` for a scrub jump.
                4. Wait up to 2 seconds for the worker to supply the frame.
                5. Return the frame or ``None`` on timeout.

            Side effects: updates ``playback.current_frame_index`` and
            ``current_frame_data`` when a frame is retrieved.

        Returns:
            RGBFrame | None: The requested frame, or ``None`` if it is unavailable.
        """
        import time

        session_state = self.state
        max_idx = max(session_state.metadata.frame_count - 1, 0)
        safe_idx = max(0, min(frame_index, max_idx))

        decode_worker = self.video_decode_worker

        # ====================================
        # 1. Check if frame at index is cached
        # ====================================
        # cached_frame = decode_worker.ring_buffer.get(safe_idx)
        # [NEW] Bypass directly accessing the ring buffer
        cached_frame = decode_worker.get_cached_frame_at_index(safe_idx)

        if cached_frame is not None:
            # Update session state and return cached frame
            session_state.playback.current_frame_index = safe_idx
            session_state.current_frame_data = cached_frame
            return cached_frame

        # ====================================
        # 2. Cache Miss
        # ====================================
        # Check if this is a normal sequential playback (worker just fell a few ms behind)
        is_sequential_underrun = abs(safe_idx - session_state.playback.current_frame_index) <= 1

        if not is_sequential_underrun:
            # The user actually scrubbed the timeline. Force an expensive Hard Seek.
            decode_worker.request_seek(safe_idx)
        # else:
        #   It IS underrun, do nothing.
        #   Let the worker finish its sequential decoding.

        # ====================================
        # 3. Wait for worker to catch up
        # ====================================

        # TODO:
        #       Extract the timeout-loop out of `Session` and
        #       move it into the `VideoDecodeWorker` (or a new `FrameSynchronizer` class).
        #       The worker should be responsible for managing its own thread delays.
        attempts = 0
        while attempts < 200:  # 2.0 second timeout
            # cached_frame = decode_worker.ring_buffer.get(safe_idx)
            cached_frame = decode_worker.get_cached_frame_at_index(safe_idx)
            if cached_frame is not None:
                # [NEW] Use the new method
                self.state.update_current_frame_data_and_index(idx=safe_idx, frame_data=cached_frame)
                return cached_frame
            time.sleep(0.01)
            attempts += 1

        logger.error("Timeout waiting for worker to supply frame {}", safe_idx)
        return None

    def get_current_frame(self) -> RGBFrame | None:
        """Get frame at current playback position (caches result in state)."""
        current_index = self.state.playback.current_frame_index

        # FIX: Ensure we actually update and return the fallback data if empty!
        if self.state.current_frame_data is None:
            self.state.current_frame_data = self.get_frame_by_index(current_index)

        return self.state.current_frame_data

    def get_next_frame(self) -> RGBFrame | None:
        """Get next frame (current_idx + 1)."""
        return self.get_frame_by_index(self.state.playback.current_frame_index + 1)

    def get_previous_frame(self) -> RGBFrame | None:
        """Get previous frame (current_idx - 1)."""
        return self.get_frame_by_index(self.state.playback.current_frame_index - 1)

    def reset_model(self, model_name: str, keep_manual: bool = False) -> None:
        """
        Change the detection model and clear Layers B and D.

        Note:
            If ``model_name == "None"``, all layers (A, B, C, and D) are cleared.
            Otherwise the new model name is stored and Layers B and D are cleared while
            optionally preserving manual annotations.
        """

        if model_name == "None":
            logger.info("Deleting detection engine and session layers for Session: '{}'", self.s_id)
            self.data.clear_all_layers(keep_manual=keep_manual)
            return

        self.state.settings.detection_model_name = model_name
        self.data.clear_layer_by_name(VideoDataLayer.B, keep_manual)
        self.data.clear_layer_by_name(VideoDataLayer.D, keep_manual)

        logger.info("Detection model set for session '{}'. Layers cleared.", self.s_id)
