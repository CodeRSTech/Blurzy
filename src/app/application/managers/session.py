"""
Module for session; coordinates session and worker lifecycles.

See Also:
    - [`SessionInitializer`][app.application.managers.session_initializer.SessionInitializer] — attaches runtime collaborators to new sessions
    - [`Session`][app.infrastructure.session.session.Session] — infrastructure runtime object managed here

Layer: Application.
Context: Coordinates session and worker lifecycles at this architectural boundary.
"""

from __future__ import annotations

from typing import override, TYPE_CHECKING

from app.application.managers.session_initializer import SessionInitializer
from app.domain.session import SessionId
from app.infrastructure.session.session import Session
from app.infrastructure.video.reader import ZeroStreamsInVideoException
from app.shared.exceptions import SessionAlreadyExistsException, VideoFileOpenException, VideoStreamStateException
from app.shared.logging_cfg import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterable
    from app.application.application import Application
    from app.infrastructure.dtypes import RGBFrame
    from app.domain.session.session_state import SessionState

logger = get_logger("Application->SessionManager")


class SessionManager:
    """
    Owns the `dict` of open `Session` objects and coordinates their
    application-layer lifecycle.

    The manager keeps session creation and initialization in one place, while
    the expensive runtime bootstrap (video reader, runtime view_state, decode
    worker) is delegated to `SessionInitializer`.


    Layer: Application.
    Context: Coordinates use-case behavior through domain services and application contracts.


    Args:
        app: Application that owns the manager and is notified when the active session changes.
        session_initializer: Initializer that constructs and wires new sessions.
    """

    def __init__(self, app: Application, session_initializer: SessionInitializer | None = None) -> None:
        logger.debug("Initializing SessionManager...")
        self._app = app
        self._session_svc = None
        self._sessions: dict[SessionId, Session] = {}
        self._active_s_id: SessionId = SessionId("")
        self._session_initializer = session_initializer or SessionInitializer()

        logger.debug("SessionManager initialized.")

    @override
    def __repr__(self) -> str:
        return f"SessionManager<sessions={len(self._sessions)}, active={self._active_s_id}>"

    # ---------- ACTIVE SESSION PROPERTIES ----------

    @property
    def active_session(self) -> Session | None:
        """
        Return the currently active session, if any.

        Returns:
            Active session, or `None` when no session is active.
        """
        if not self._active_s_id:
            # raise LookupError("No active session was found, try opening video(s).")
            # [NOTE] This was disabled because
            return None
        return self.get_session_by_id(self._active_s_id)

    @property
    def active_session_id(self) -> SessionId | None:
        """
        Return the identifier of the active session, if any.

        Returns:
            Active session identifier, or `None` when no session is active.
        """
        return self._active_s_id

    @active_session_id.setter
    def active_session_id(self, s_id: SessionId) -> None:
        """
        Activate a session and notify the application when it changes.

        Args:
            s_id: Identifier of the session to activate.
        """
        logger.debug("Setting active session: {}", s_id)
        old_s_id = None
        if self._active_s_id and self._active_s_id != s_id:
            logger.debug("Deactivating Video Decode Worker for previous session: {}", self._active_s_id)
            # self.deactivate_video_decode_worker_for_session_id(self._active_s_id)
            old_s_id = self._active_s_id
        elif self._active_s_id == s_id:
            logger.trace("Active session already set: {}", s_id)
            return

        self._active_s_id = s_id
        logger.info("Active session set: {}", s_id)

        # 3. WAKE UP THE NEW WORKER (Allocates memory for the active video buffer)
        # self.activate_video_decode_worker_for_session_id(s_id)
        self._app.handle_active_session_changed(old_s_id=old_s_id, new_s_id=s_id)

    @property
    def all_session_ids(self) -> Iterable[SessionId]:
        """
        Return identifiers for all managed sessions.

        Returns:
            An iterable view of the managed session identifiers.
        """
        return self._sessions.keys()

    @property
    def all_sessions(self) -> Iterable[Session]:
        """
        Return all sessions managed by this manager.

        Returns:
            An iterable view of the managed session objects.
        """
        return self._sessions.values()

    def bind_session_service(self, session_service):
        """
        Bind the session service used for session lifecycle operations.

        Args:
            session_service: Service used to coordinate session lifecycle workflows.
        """
        self._session_svc = session_service

    def create_session_from_video_path(self, path: str):
        """
        Create and register a session for a video file.

        Args:
            path: Filesystem path of the video to open.

        Note:
            Duplicate paths are rejected; video-open and stream errors are logged
            and skipped without creating a session.
        """
        logger.info("Creating new session for video: {}", path)

        new_s_id = SessionId(path)
        if new_s_id in self._sessions:
            raise SessionAlreadyExistsException("Error while opening video from path.", path)

        try:
            session = Session(new_s_id)
            self._session_initializer.initialize(session)
            self._sessions[new_s_id] = session
            logger.debug("Created session: id={}", path)
        except ZeroStreamsInVideoException:
            # [NOTE] Whilst catching the exception here will work,
            # re-raising it might not allow other videos to load properly
            # likely caused by whatever that's calling THIS method.
            logger.error("Zero streams were found while opening video from path: '{}'. Skipping...", path)
        except (VideoFileOpenException, VideoStreamStateException) as exc:
            logger.warning("Failed to create session for video: {}; skipped creating session. {}", path, exc)

    def get_session_by_id(self, s_id: SessionId) -> Session:
        """
        Return the session identified by `s_id`.

        Args:
            s_id: Identifier of the session to retrieve.

        Returns:
            Matching session.

        Raises:
            KeyError: If `s_id` is not managed by this manager.
        """
        session = self._sessions.get(s_id)
        if session is None:
            logger.error("Attempted to get view_state for unknown Session ID: {}", s_id)
            raise KeyError(f"Unknown session id: {s_id}, available: {list(self._sessions.keys())}")
        return session

    def discard_session(self, s_id: SessionId) -> None:
        """
        Close and remove the session identified by its session ID.

        Args:
            s_id: Identifier of the session to close and remove.
        """
        session = self._sessions.pop(s_id, None)
        if session is None:
            return
        logger.warning("Discarding session '{}'", s_id)
        session.close()
        if self._active_s_id == s_id:
            if self._sessions:
                self._active_s_id = next(iter(self._sessions.keys()))
            else:
                self._active_s_id = SessionId("")

    def get_session_state_by_id(self, s_id: SessionId) -> SessionState:
        """
        Return the state object belonging to `s_id`.

        Args:
            s_id: Identifier of the session to inspect.

        Returns:
            The `SessionState` for `s_id`, including its playback, settings, and
            annotation state.
        """
        return self.get_session_by_id(s_id).state

    def initialize_active_session(self):
        """
        One-time helper to initialize the active session.
"""
        if self._sessions:
            self.active_session_id = next(iter(self._sessions.keys()))
            logger.info("Active session initialized: {}", self.active_session_id)

    def close_all(self) -> None:
        """
        Closes all sessions and clears the session manager.

        Flow:
            1. Iterate through all sessions and call their `close()` method.
            2. Clear the internal session dictionary.
            3. Reset the active session ID to an empty view_state using `SessionId("")`.

        """
        logger.info("SessionManager closing all sessions")

        for session in self._sessions.values():
            session.close()

        self._sessions.clear()
        self._active_s_id = SessionId("")

    # ============================== FRAME GETTERS ==============================

    def stop_all_playback(self) -> None:
        """
        Stop all playback.
"""
        logger.trace("Stopping all playback sessions")
        for session in self._sessions.values():
            session.stop_playback()
        logger.trace("Stopped playback for all sessions")

    def get_frame_for_session_id_by_index(self, frame_index: int, s_id: SessionId) -> RGBFrame | None:
        """
        Fetches a specific frame directly from the O(1) Ring Buffer, or triggers a seek.

        Args:
            frame_index: Zero-based frame index to retrieve.
            s_id: Identifier of the session containing the frame.

        Returns:
            Decoded RGB frame, or `None` if it is unavailable.
        """
        session = self.get_session_by_id(s_id)
        return session.get_frame_by_index(frame_index)

    def get_current_frame_for_session_id(self, s_id: SessionId) -> RGBFrame | None:
        """
        Retrieve the frame at the session's current playback index.

        Args:
            s_id: Identifier of the session to query.

        Returns:
            Cached or decoded RGB frame, or `None` if no frame is available.
        """
        return self.get_session_by_id(s_id).get_current_frame()

    def get_next_frame_for_session_id(self, s_id: SessionId) -> RGBFrame | None:
        """
        Advance the session to its next frame and retrieve it.

        Args:
            s_id: Identifier of the session to advance.

        Returns:
            Next RGB frame, or `None` if no frame is available.
        """
        return self.get_session_by_id(s_id).get_next_frame()

    def get_previous_frame_for_session_id(self, s_id: SessionId) -> RGBFrame | None:
        """
        Move the session to its previous frame and retrieve it.

        Args:
            s_id: Identifier of the session to rewind.

        Returns:
            Previous RGB frame, or `None` if no frame is available.
        """
        return self.get_session_by_id(s_id).get_previous_frame()
