from __future__ import annotations

from typing import TYPE_CHECKING



from typing import override, TYPE_CHECKING

from app.application.managers.session_initializer import SessionInitializer
from app.domain.session import SessionId
from app.infrastructure.session.session import Session
from app.infrastructure.video.reader import ZeroStreamsInVideoException
from app.shared.exceptions import SessionAlreadyExistsException, VideoFileOpenException, VideoStreamStateException
from app.shared.logging_cfg import get_logger
if TYPE_CHECKING:
    from collections.abc import Iterable


if TYPE_CHECKING:
    from app.application.application import Application
    from app.infrastructure.dtypes import RGBFrame
    from app.domain.session.session_state import SessionState

logger = get_logger("Application->SessionManager")


class SessionManager:
    """
    Owns the ``dict`` of open ``Session`` objects and coordinates their
    application-layer lifecycle.

    The manager keeps session creation and initialization in one place, while
    the expensive runtime bootstrap (video reader, runtime view_state, decode
    worker) is delegated to ``SessionInitializer``.
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
        if not self._active_s_id:
            # raise LookupError("No active session was found, try opening video(s).")
            # [NOTE] This was disabled because
            return None
        return self.get_session_by_id(self._active_s_id)

    @property
    def active_session_id(self) -> SessionId | None:
        return self._active_s_id

    @active_session_id.setter
    def active_session_id(self, s_id: SessionId) -> None:
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
        return self._sessions.keys()

    @property
    def all_sessions(self) -> Iterable[Session]:
        return self._sessions.values()

    def bind_session_service(self, session_service):
        self._session_svc = session_service

    def create_session_from_video_path(self, path: str):
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
        session = self._sessions.get(s_id)
        if session is None:
            logger.error("Attempted to get view_state for unknown Session ID: {}", s_id)
            raise KeyError(f"Unknown session id: {s_id}, available: {list(self._sessions.keys())}")
        return session

    def get_session_state_by_id(self, s_id: SessionId) -> SessionState:
        return self.get_session_by_id(s_id).state

    def initialize_active_session(self):
        """One-time helper to initialize the active session."""
        if self._sessions:
            self.active_session_id = next(iter(self._sessions.keys()))
            logger.info("Active session initialized: {}", self.active_session_id)

    def close_all(self) -> None:
        """
        Closes all sessions and clears the session manager.

        Flow:
            1. Iterate through all sessions and call their ``close()`` method.
            2. Clear the internal session dictionary.
            3. Reset the active session ID to an empty view_state using ``SessionId("")``.

        """
        logger.info("SessionManager closing all sessions")

        for session in self._sessions.values():
            session.close()

        self._sessions.clear()
        self._active_s_id = SessionId("")

    # ============================== FRAME GETTERS ==============================

    def stop_all_playback(self) -> None:
        logger.trace("Stopping all playback sessions")
        for session in self._sessions.values():
            session.stop_playback()
        logger.trace("Stopped playback for all sessions")

    def get_frame_for_session_id_by_index(self, frame_index: int, s_id: SessionId) -> RGBFrame | None:
        """Fetches a specific frame directly from the O(1) Ring Buffer, or triggers a seek."""
        session = self.get_session_by_id(s_id)
        return session.get_frame_by_index(frame_index)

    def get_current_frame_for_session_id(self, s_id: SessionId) -> RGBFrame | None:
        """Retrieve the current frame index and the CACHED frame data."""
        return self.get_session_by_id(s_id).get_current_frame()

    def get_next_frame_for_session_id(self, s_id: SessionId) -> RGBFrame | None:
        return self.get_session_by_id(s_id).get_next_frame()

    def get_previous_frame_for_session_id(self, s_id: SessionId) -> RGBFrame | None:
        return self.get_session_by_id(s_id).get_previous_frame()
