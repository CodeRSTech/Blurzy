"""
Interface contract for session repository / session access.

See Also:
    - [`Application`][app.application.application.Application] — provides the concrete application operations
    - [`ApplicationAdapter`][app.application.adapters.application_adapter.ApplicationAdapter] — adapts the concrete application to this contract

Layer: Application.
Context: Defines protocol boundaries consumed by application orchestration.
"""

from __future__ import annotations


from typing import TYPE_CHECKING, Protocol
if TYPE_CHECKING:
    from collections.abc import Iterable
    from app.domain import VideoDataLayerGroup, FrameBoxesViewModel, VideoDataLayer, BBoxViewModel



if TYPE_CHECKING:
    from app.domain.session import SessionId
    from app.infrastructure.session.session import Session


class UIApplicationInterface(Protocol):
    """
    Abstraction boundary for accessing and managing sessions.

    Services and managers depend on this interface rather than directly
    importing the concrete `Application` class, keeping the application layer
    decoupled from the top-level façade.

    The concrete `Application` class satisfies this interface structurally
    (structural subtyping via `Protocol`) — no explicit inheritance needed.
    The `AppApplicationAdapter` provides an explicit wrapper when
    explicit type evidence is preferred.


    Layer: Application.
    Context: Coordinates use-case behavior through domain services and application contracts.
    """

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
    #                            PROPERTIES
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

    @property
    def active_session(self) -> Session | None:
        """
        Retrieve the currently active `Session` instance, or `None` if no session is active.

        Returns:
            The active session, or `None` if there is no active session.
        """
        ...

    @property
    def active_session_id(self) -> SessionId | None:
        """
        Return the `SessionId` of the currently active session, or `None`.

        Returns:
            The active session identifier, or `None` if none is active.
        """
        ...

    @property
    def all_s_ids(self) -> Iterable[SessionId]:
        """
        Iterate over all `SessionId` instances currently managed by the application.

        Returns:
            Identifiers for sessions currently managed by the application.
        """
        ...

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
    #                        METHODS
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

    def get_session_by_id(self, s_id: SessionId) -> Session:
        """
        Fetch the `Session` instance identified by `s_id`.

        Args:
            s_id: Identifier of the session to return.

        Returns:
            The session identified by `s_id`.
        """
        ...

    # Used by PlaybackHandler
    def is_at_last_frame(self, s_id: SessionId) -> bool:
        """
        Check if the playback position for `s_id` is at the final frame.

        Args:
            s_id: Identifier of the session whose playback position is checked.

        Returns:
            `True` when playback is positioned at the final frame.
        """
        ...

    # Used by PlaybackHandler
    def is_session_playing(self, s_id: SessionId) -> bool:
        """
        Check if the `Session` identified by `s_id` is currently playing.

        Args:
            s_id: Identifier of the session whose playback state is inspected.

        Returns:
            `True` while the session's playback state is active.
        """
        ...

    # Used by UIHandler
    def get_tab_frame_boxes_for_session_id(
            self, s_id: SessionId, tab: VideoDataLayerGroup
    ) -> FrameBoxesViewModel:
        """
        Retrieve all bounding boxes for the current frame in the specified `tab` layer.

        Args:
            s_id: Identifier of the session whose current frame is queried.
            tab: Detection or tracking tab selecting its editable box layer.

        Returns:
            Frame-box view model for the selected tab and current frame.
        """
        ...

    # Used by AnnotationHandler
    def get_layer_box_by_key(
            self, s_id: SessionId, layer_name: VideoDataLayer, key: str
    ) -> BBoxViewModel | None:
        """
        Fetch a single bounding detection by its unique `key` from `layer_name`.

        Args:
            s_id: Identifier of the session containing the box.
            layer_name: Data layer in which to search.
            key: Unique box key to match.

        Returns:
            Matching box view model, or `None` if the layer has no box with this key.
        """
        ...

    # Used by ModelHandler
    def get_selected_detection_model_name(self, s_id: SessionId) -> str:
        """
        Retrieve the name of the currently selected detection model for `s_id`.

        Args:
            s_id: Identifier of the session whose configured model name is returned.

        Returns:
            Name of the selected detection model.
        """
        ...

    # Used by ExportHandler
    def session_is_ready_for_export(self, s_id: SessionId) -> bool:
        """
        Check if the session `s_id` has valid tracking data and is ready to export.

        Args:
            s_id: Identifier of the session whose tracking data is checked for export.

        Returns:
            `True` when the session has tracking data that can be exported.
        """
        ...

    # Used by SessionHandler
    def open_videos(self, paths: Iterable[str]) -> list[str]:
        """
        Create new `Session` instances from video files at the given `paths`.

        Args:
            paths: Video file paths to open.

        Returns:
            Paths of videos opened successfully; already-open paths are excluded.
        """
        ...

    # Used by PlaybackHandler
    def session_has_buffered_frame(self, s_id: SessionId) -> bool:
        """
        Check if a pre-decoded frame is available in the buffer for `s_id`.

        Args:
            s_id: Identifier of the session whose decode buffer is inspected.

        Returns:
            `True` when the session's decode buffer contains a readable frame.
        """
        ...

    def session_has_running_detection_worker(self, s_id: SessionId) -> bool:
        """
        Check if a `DetectionWorker` is actively running for `s_id`.

        Args:
            s_id: Identifier of the session whose detection worker state is queried.

        Returns:
            `True` when a detection worker is running.
        """
        ...

    # Used by TrackingHandler
    def session_has_running_tracking_worker(self, s_id: SessionId) -> bool:
        """
        Check if a `TrackingWorker` is actively running for `s_id`.

        Args:
            s_id: Identifier of the session whose tracking worker state is queried.

        Returns:
            `True` when a tracking worker is running.
        """
        ...
