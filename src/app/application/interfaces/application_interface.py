"""Interface contract for session repository / session access."""

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
    importing the concrete ``Application`` class, keeping the application layer
    decoupled from the top-level façade.

    The concrete ``Application`` class satisfies this interface structurally
    (structural subtyping via ``Protocol``) — no explicit inheritance needed.
    The ``AppApplicationAdapter`` provides an explicit wrapper when 
    explicit type evidence is preferred.
    """

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
    #                            PROPERTIES
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

    @property
    def active_session(self) -> Session | None:
        """Retrieve the currently active ``Session`` instance, or ``None`` if no session is active."""
        ...

    @property
    def active_session_id(self) -> SessionId | None:
        """Return the ``SessionId`` of the currently active session, or ``None``."""
        ...

    @property
    def all_s_ids(self) -> Iterable[SessionId]:
        """Iterate over all ``SessionId`` instances currently managed by the application."""
        ...

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
    #                        METHODS
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

    def get_session_by_id(self, s_id: SessionId) -> Session:
        """Fetch the ``Session`` instance identified by ``s_id``."""
        ...

    # Used by PlaybackHandler
    def is_at_last_frame(self, s_id: SessionId) -> bool:
        """Check if the playback position for ``s_id`` is at the final frame."""
        ...

    # Used by PlaybackHandler
    def is_session_playing(self, s_id: SessionId) -> bool:
        """Check if the ``Session`` identified by ``s_id`` is currently playing."""
        ...

    # Used by UIHandler
    def get_tab_frame_boxes_for_session_id(
            self, s_id: SessionId, tab: VideoDataLayerGroup
    ) -> FrameBoxesViewModel:
        """Retrieve all bounding boxes for the current frame in the specified ``tab`` layer."""
        ...

    # Used by AnnotationHandler
    def get_layer_box_by_key(
            self, s_id: SessionId, layer_name: VideoDataLayer, key: str
    ) -> BBoxViewModel | None:
        """Fetch a single bounding detection by its unique ``key`` from ``layer_name``."""
        ...

    # Used by ModelHandler
    def get_selected_detection_model_name(self, s_id: SessionId) -> str:
        """Retrieve the name of the currently selected detection model for ``s_id``."""
        ...

    # Used by ExportHandler
    def session_is_ready_for_export(self, s_id: SessionId) -> bool:
        """Check if the session ``s_id`` has valid tracking data and is ready to export."""
        ...

    # Used by SessionHandler
    def open_videos(self, paths: Iterable[str]) -> list[str]:
        """Create new ``Session`` instances from video files at the given ``paths``."""
        ...

    # Used by PlaybackHandler
    def session_has_buffered_frame(self, s_id: SessionId) -> bool:
        """Check if a pre-decoded frame is available in the buffer for ``s_id``."""
        ...

    def session_has_running_detection_worker(self, s_id: SessionId) -> bool:
        """Check if a ``DetectionWorker`` is actively running for ``s_id``."""
        ...

    # Used by TrackingHandler
    def session_has_running_tracking_worker(self, s_id: SessionId) -> bool:
        """Check if a ``TrackingWorker`` is actively running for ``s_id``."""
        ...
