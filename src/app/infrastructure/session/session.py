"""
Container for a single video file session, holding the runtime state and layer storage.

The expensive runtime collaborators
([`VideoReader`][app.infrastructure.video.reader.VideoReader],
[`SessionState`][app.domain.session.session_state.SessionState]
and the
[`VideoDecodeWorker`][app.infrastructure.video.decode_worker.VideoDecodeWorker])
are attached by
[`SessionInitializer`][app.application.managers.session_initializer.SessionInitializer]
in the [`Application layer`][app.application].

See Also:
    - [`SessionDataStore`][app.infrastructure.session.session_data_store.SessionDataStore] — layer storage
    - [`SessionFrameAccessor`][app.infrastructure.session.frame_access.SessionFrameAccessor] — frame access and ring-buffer logic


??? warning "Design considerations"

    `Session` is a runtime facade, but it still has several reasons to change. It
    coordinates collaborator initialization state and shutdown, exposes playback
    and frame access, forwards layer-storage operations, and changes detection
    settings and layer contents. This is a potential **Single Responsibility
    Principle (SRP)** violation: those responsibilities may evolve for different
    reasons. Delegating frame access to
    [`SessionFrameAccessor`][app.infrastructure.session.frame_access.SessionFrameAccessor]
    and storage to
    [`SessionDataStore`][app.infrastructure.session.session_data_store.SessionDataStore]
    reduces the concentration of logic, but `Session` remains the entry point for
    all of these concerns.

    There is some potential **DRY** duplication in repeatedly requiring the
    session state and decode worker before frame operations. The `_require_*`
    helpers centralize the checks, however, so this is limited duplication rather
    than necessarily a design flaw.

    There may also be a **Dependency Inversion Principle (DIP)** concern: `Session`
    constructs concrete infrastructure collaborators and is coupled to `QObject`.
    That can make substitution and isolated testing harder. Whether this is a
    violation depends on the intended boundary: as an infrastructure-level
    component, `Session` may appropriately depend on infrastructure details, but
    higher-level policy should avoid depending on those concrete details.

    Finally, `Session` exposes a broad API spanning workers, playback, frames, and
    layers. That can indicate an **Interface Segregation Principle (ISP)** concern
    for clients that need only one of those capabilities. These are design tradeoffs
    to assess against actual change and testing needs, not automatic violations.


Layer: Infrastructure.
Context: Implements concrete processing and I/O behind application-facing contracts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from PySide6.QtCore import QObject

from app.domain import VideoDataLayer
from app.shared.logging_cfg import get_logger
from app.infrastructure.session.session_data_store import SessionDataStore
from app.infrastructure.session.frame_access import SessionFrameAccessor

if TYPE_CHECKING:
    from app.domain import SessionState
    from app.domain.session import SessionId
    from app.domain.base.dtypes import ListOfBoxesByFrameIndexAsDict, ListOfBoxes
    from app.infrastructure.dtypes import RGBFrame
    from app.infrastructure.video.decode_worker import VideoDecodeWorker
    from app.infrastructure.video.reader import VideoReader

logger = get_logger("Domain->Session")


@final
class Session(QObject):
    """
    Container holding the runtime view_state and layer storage for a single video
    processing session.

    `Session` stays a `QObject` for now and keeps a narrow runtime role:
    it owns IDs, layer storage, collaborator references, and thin convenience
    methods. Expensive initialization and frame-orchestration logic are
    delegated to dedicated collaborators.

    Attributes:
        s_id: Identifier for this session.
        data: Layer storage associated with this session.
        video_reader: Video reader, attached during session initialization.
        state: Playback and settings state, attached during session initialization.
        video_decode_worker: Worker that decodes video frames.
        _frame_accessor: Helper that coordinates frame access.
        detection_engine: Detection engine used by the session, if initialized.
        detection_worker: Detection worker, if initialized.
        tracking_worker: Tracking worker, if initialized.


    Layer: Infrastructure.
    Context: Implements concrete processing or I/O behind application-facing contracts.


    Args:
        s_id: Identifier of the session associated with this object.
    """

    def __init__(self, s_id: SessionId) -> None:
        """
        Create a bare session shell.

        The initializer is responsible for attaching the runtime collaborators
        later. This keeps object construction predictable and easy to test.
        """
        super().__init__()

        self.s_id = s_id
        self.data = SessionDataStore(s_id=self.s_id, parent=self)
        self.video_reader = None
        self.state = None
        self.video_decode_worker = None
        self._frame_accessor = SessionFrameAccessor()
        self.detection_engine = None
        self.detection_worker = None
        self.tracking_worker = None

    def __repr__(self):
        return f"<Session id={self.s_id.basename}>"

    def _require_state(self) -> SessionState:
        """
        Return the initialized session view_state or raise a clear error.
        """
        if self.state is None:
            raise RuntimeError(
                "Session view_state has not been initialized yet. "
                "Use SessionInitializer.initialize(session) before accessing playback or frame data."
            )
        return self.state

    def _require_video_reader(self) -> VideoReader:
        """
        Return the initialized video reader or raise a clear error.
        """
        if self.video_reader is None:
            raise RuntimeError(
                "Session video reader has not been initialized yet. "
                "Use SessionInitializer.initialize(session) before reading frames."
            )
        return self.video_reader

    def _require_video_decode_worker(self) -> VideoDecodeWorker:
        """
        Return the initialized decode worker or raise a clear error.
        """
        if self.video_decode_worker is None:
            raise RuntimeError(
                "Session decode worker has not been initialized yet. "
                "Use SessionInitializer.initialize(session) before reading buffered frames."
            )
        return self.video_decode_worker

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """
 ### PROPERTIES """
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    @property
    def has_buffered_frame(self) -> bool:
        """
        Check if the session has a buffered frame.

        Returns:
            `True` when the decode worker can provide a buffered frame.
        """
        return self.get_buffered_frame() is not None

    @property
    def has_running_detection_worker(self) -> bool:
        """
        Check if the session has a running detection worker.

        Returns:
            `True` when the detection worker exists and is running.
        """
        return self.detection_worker is not None and self.detection_worker.isRunning()

    @property
    def has_running_tracking_worker(self) -> bool:
        """
        Check if the session has a running tracking worker.

        Returns:
            `True` when the tracking worker exists and is running.
        """
        return self.tracking_worker is not None and self.tracking_worker.isRunning()

    @property
    def is_playing_video(self) -> bool:
        """
        Check if the session is currently playing the video.

        Returns:
            Whether the session is currently playing.
        """
        return self._require_state().playback.is_playing

    @is_playing_video.setter
    def is_playing_video(self, is_playing: bool) -> None:
        """
        Set whether this session's playback is active.

        Args:
            is_playing: Whether playback should be active.
        """
        self._require_state().playback.is_playing = is_playing

    def close(self) -> None:
        """
        Stop all workers (detection, tracking, decode) and close reader.
        """
        if self.detection_worker is not None:
            self.detection_worker.stop()
        if self.tracking_worker is not None:
            self.tracking_worker.stop()
        if self.video_decode_worker is not None:
            self.video_decode_worker.stop()

        if self.video_reader is not None:
            self.video_reader.close()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #                            LAYER CRUD MANAGEMENT
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def get_layer_by_name(self, layer_name: VideoDataLayer) -> ListOfBoxesByFrameIndexAsDict:
        """
        Get all boxes for a specific layer as a dictionary of lists.

        Args:
            layer_name: Layer whose boxes should be retrieved.

        Returns:
            Mapping of frame indices to the layer's boxes for those frames.
        """
        return self.data.get_all_boxes_for_layer_as_dict_of_lists(layer_name)

    def get_layer_boxes_for_index(self, layer_name: VideoDataLayer, frame_index: int) -> ListOfBoxes:
        """
        Get all boxes for a specific layer at a specific frame index.

        Args:
            layer_name: Layer to query.
            frame_index: Zero-based frame index to query.

        Returns:
            Boxes stored in the layer at that frame, or an empty list if none are stored.
        """
        # Natively fetches the list directly from the Pandas dataframe!
        return self.data.get_boxes_for_layer_at_frame_index_as_list(layer_name, frame_index)

    def get_layer_boxes_for_current_frame(self, layer_name: VideoDataLayer) -> ListOfBoxes:
        """
        Get all boxes for a specific layer at the current playback frame index.

        Args:
            layer_name: Layer to query.

        Returns:
            Boxes stored in the layer at the current playback index.
        """
        return self.get_layer_boxes_for_index(layer_name, self._require_state().playback.current_frame_index)

    def has_boxes_for_layer(self, layer_name: VideoDataLayer) -> bool:
        """
        Check if there are any boxes for a specific layer.

        Args:
            layer_name: Name of the target layer.

        Returns:
            `True` when the layer contains boxes.
        """
        return self.data.has_boxes_for_layer(layer_name)

    def stop_playback(self):
        """
        Stop video playback and reset the playback state.
        """
        self._require_state().playback.stop_playback()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #                           FRAME CONTROLS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def get_buffered_frame(self) -> RGBFrame | None:
        """
        Get the next frame (current_idx + 1) from the ring buffer (for lookahead during playback).

        Returns:
            Next RGB frame, or `None` if it is not currently available.

        Note:
            The frame accessor updates playback state when the frame is retrieved.
        """
        return self._frame_accessor.get_buffered_frame(
            session_state=self._require_state(),
            decode_worker=self._require_video_decode_worker(),
        )

    def get_frame_by_index(self, frame_index: int) -> RGBFrame | None:
        """
        Fetch frame at `frame_index` from the ring buffer cache with timeout-based seek handling.

        Workflow:
            1. Clamp `frame_index` to the valid range.
            2. Check the ring buffer cache and return immediately on a hit.
            3. On a miss, either wait for sequential playback to catch up or trigger
                   `request_seek()` for a scrub jump.
            4. Wait up to 2 seconds for the worker to supply the frame.
            5. Return the frame or `None` on timeout.

        !!! warning "Side effects"
            updates `playback.current_frame_index` and
            `current_frame_data` when a frame is retrieved.

        Returns:
            RGBFrame | None: The requested frame, or `None` if it is unavailable.
        """
        return self._frame_accessor.get_frame_by_index(
            session_state=self._require_state(),
            decode_worker=self._require_video_decode_worker(),
            frame_index=frame_index,
        )

    def get_current_frame(self) -> RGBFrame | None:
        """
        Get frame at current playback position (caches result in view_state).

        Returns:
            Current RGB frame, or `None` when no frame is available.

        Side Effects:
            Caches a retrieved frame in the session state.
        """
        return self._frame_accessor.get_current_frame(
            session_state=self._require_state(),
            decode_worker=self._require_video_decode_worker(),
        )

    def get_next_frame(self) -> RGBFrame | None:
        """
        Get next frame (current_idx + 1).

        Returns:
            Next RGB frame, or `None` when it is not decoded before the timeout.

        Side Effects:
            On success, advances the playback index and caches the frame.
        """
        return self._frame_accessor.get_next_frame(
            session_state=self._require_state(),
            decode_worker=self._require_video_decode_worker(),
        )

    def get_previous_frame(self) -> RGBFrame | None:
        """
        Get previous frame at index `(current_idx - 1)`.

        Returns:
            Previous RGB frame, or `None` when it is not decoded before the timeout.

        Side Effects:
            On success, moves the playback index backward and caches the frame.
        """
        return self._frame_accessor.get_previous_frame(
            session_state=self._require_state(),
            decode_worker=self._require_video_decode_worker(),
        )

    def reset_model(self, model_name: str, keep_manual: bool = False) -> None:
        """
        Change the detection model and clear Layers B and D.

        Note:
            If `model_name == "None"`, all layers (A, B, C, and D) are cleared.
            Otherwise the new model name is stored and Layers B and D are cleared while
            optionally preserving manual annotations.
        """

        if model_name == "None":
            logger.info("Deleting detection engine and session layers for Session: '{}'", self.s_id)
            self.data.clear_all_layers(keep_manual=keep_manual)
            return

        self._require_state().settings.detection_model_name = model_name
        self.data.clear_layer_by_name(VideoDataLayer.B, keep_manual)
        self.data.clear_layer_by_name(VideoDataLayer.D, keep_manual)

        logger.info("Detection model set for session '{}'. Layers cleared.", self.s_id)
