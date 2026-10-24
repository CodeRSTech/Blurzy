"""
Explicit adapter wrapping `Application` to `ApplicationInterface`.

???+ note "Important Note"
    All methods of `ApplicationAdapter` are intended for use **only** by application services.

See Also:
    - [`Application`][app.application.application.Application] — provides the concrete workflow operations
    - [`UIApplicationInterface`][app.application.interfaces.application_interface.UIApplicationInterface] — defines the contract exposed to callers

Layer: Application.
Context: Adapts infrastructure implementations to application contracts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.interfaces import UIApplicationInterface
if TYPE_CHECKING:
    from collections.abc import Iterable
    from app.application.application import Application
    from app.domain.session.session_id import SessionId
    from app.infrastructure.session.session import Session


class ApplicationAdapter(UIApplicationInterface):
    """
    Explicit adapter that wraps the top-level `Application` façade and exposes only
    the `ApplicationInterface` contract used by services and managers.

    The `Application` class already satisfies `ApplicationInterface` via
    structural subtyping (`Protocol`), so this adapter is not required for
    runtime correctness.  It exists to:

    - Provide an explicit, typed boundary between the application façade and
      the components that need only session access.
    - Make session-repository dependencies visible and mockable in tests
      without depending on the entire `Application` instance.

    Layer: Application.
    Context: Coordinates use-case behavior through domain services and application contracts.

    Args:
        app: Concrete application wrapped to expose the session operations required by application services.
    """

    def __init__(self, app: Application) -> None:
        self._app = app
        self._sm = app.sm

    def __repr__(self) -> str:
        return f"<ApplicationAdapter wrapping={self._app!r}>"

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
        return self._sm.active_session

    @property
    def active_session_id(self) -> SessionId | None:
        """
        Retrieve the `SessionId` of the currently active session, or `None` if none is active.

        Returns:
            The active session identifier, or `None` if none is active.
        """
        return self._sm.active_session_id

    @active_session_id.setter
    def active_session_id(self, s_id: SessionId) -> None:
        """
        Set the active session by `SessionId`.

        Args:
            s_id: Identifier of the session to activate.
        """
        self._sm.active_session_id = s_id

    @property
    def all_s_ids(self) -> Iterable[SessionId]:
        """
        Iterate over all `SessionId` instances currently managed by the application.

        Returns:
            Iterable view of the managed session identifiers.
        """
        return self._sm.all_session_ids

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
    #                       SESSION MANAGER DELEGATION METHODS
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

    def open_video_from_path(self, path: str) -> None:
        """
        Open a video file and create a new session from `path`.

        Args:
            path: Filesystem path of the video to open.
        """
        self._sm.create_session_from_video_path(path)

    def initialize_active_session(self) -> None:
        """
        Set the first available session as the active session.
        """
        self._sm.initialize_active_session()

    def get_session_by_id(self, s_id: SessionId) -> Session:
        """
        Fetch the `Session` instance identified by `s_id`.

        Args:
            s_id: Identifier of the target session.

        Returns:
            The session identified by `s_id`.
        """
        return self._sm.get_session_by_id(s_id)

    def set_session_state_is_playing(self, s_id: SessionId, is_playing: bool) -> None:
        """
        Set the playback view_state (playing/paused) for the session `s_id`.

        Args:
            s_id: Identifier of the session whose playback state to update.
            is_playing: `True` to play the session; `False` to pause it.
        """
        self._sm.get_session_state_by_id(s_id).playback.is_playing = is_playing

    # Used by PlaybackHandler and SessionHandler
    def stop_all_playback(self) -> None:
        """
        Stop playback for **all** active sessions.
        """
        self._sm.stop_all_playback()

    def get_selected_detection_model_name(self, s_id: SessionId) -> str:
        """
        Retrieve the name of the currently selected detection model for `s_id`.

        Args:
            s_id: Identifier of the session whose model selection is queried.

        Returns:
            Name of the selected detection model.
        """
        return self.get_session_by_id(s_id).state.settings.detection_model_name