"""Session lifecycle management and worker coordination service."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject

from app.application.adapters import ApplicationAdapter
from app.application.managers.video_decode_worker import VideoDecodeWorkerManager
from app.domain.session import SessionId
from app.shared import get_logger
from app.shared.exceptions import (
    SessionAlreadyExistsException,
    NoNewOpenedSessionsException,
)

if TYPE_CHECKING:
    from app.application.application import Application

logger = get_logger("Application->SessionService")


# [AUDIT] ENCAPSULATION VIOLATION: Helper function at module scope
# `_is_settings_type_compatible` is used exclusively by SessionService
# but placed at module level. This creates coupling ambiguity.
# Recommendation: Move inside SessionService as @staticmethod or to a Settings utility class.
# This improves cohesion and makes dependencies explicit.
def _is_settings_type_compatible(existing_value: object, new_value: object) -> bool:
    """Return ``True`` when *new_value* can safely replace *existing_value* in settings.

    Rules (in priority order):

    1. Identical types are always compatible.
    2. An ``int`` (non-bool) may replace a ``float`` — Python's implicit numeric
       widening makes this safe and common from UI sliders.
    3. All other type differences are considered incompatible and should be
       logged as warnings rather than silently applied.
    """
    e_type = type(existing_value)
    n_type = type(new_value)
    if e_type is n_type:
        return True
    # Allow int → float (common from UI controls producing integer values)
    if e_type is float and n_type is int and not isinstance(new_value, bool):
        return True
    return False


class SessionService(QObject):
    """
    Facade that orchestrates session open/switch/playback/settings flows.

    **Responsibilities:**

    - Open videos and create sessions from file paths
    - Handle active session switching (delegates worker lifecycle to ``VideoDecodeWorkerManager``)
    - Check worker states (detection, tracking, buffering) via ``Session`` properties
    - Update session settings with type validation

    **Architecture:**

    - Owned by App (via parent relationship)
    - Delegates actual session creation to App
    - Delegates ``VideoDecodeWorker`` activation/deactivation to ``VideoDecodeWorkerManager``
    - Does NOT create detection/tracking workers (delegates to respective services)

    **Worker Management:**

    - ``VideoDecodeWorkerManager.switch_active_session`` is the single canonical
      entry-point for worker view_state transitions.
    - Only active session's ``VideoDecodeWorker`` is truly active (buffering frames)
    - Inactive sessions' workers are paused to save CPU/memory
    - When switching sessions: old worker paused → new worker resumed
    """

    def __init__(self, app: Application):
        super().__init__(parent=app)
        # self._app = app
        # self._sm = app.sm
        # [AUDIT] DEPENDENCY INVERSION PRINCIPLE (DIP) VIOLATION
        # VideoDecodeWorkerManager(app) receives the concrete App class,
        # but should receive the SessionRepositoryInterface instead.
        # The manager only needs read-access to sessions, not the full App.
        # This breaks the Dependency Inversion Principle and makes testing harder.
        # Fix: Pass AppSessionRepositoryAdapter(app) or inject SessionRepositoryInterface.
        self._app_adapter = ApplicationAdapter(app)
        self._decode_worker_manager = VideoDecodeWorkerManager(self._app_adapter)

    def handle_active_session_changed(
        self, old_s_id: SessionId | None, new_s_id: SessionId
    ) -> None:
        """
        Coordinate worker view_state when switching to a different session.

        **Parameters:**

        - ``old_s_id`` — Previously active session ID (may be None on startup)
        - ``new_s_id`` — New active session ID

        **Flow:**

        Delegates entirely to ``VideoDecodeWorkerManager.switch_active_session``,
        which is the canonical owner of the old→new decode-worker transition:

        ``switch_active_session(old_s_id, new_s_id)`` ::

          ├── Guard: if old == new, return immediately (no duplicate churn)
          ├── If old session exists: pause its VideoDecodeWorker
          └──> Resume VideoDecodeWorker for new session

        **Purpose:**

        - Pauses old worker to save CPU (stops buffering frames)
        - Resumes new worker to start buffering its frames
        - Only one worker should be buffering at a time
        """
        self._decode_worker_manager.switch_active_session(
            old_s_id=old_s_id, new_s_id=new_s_id
        )

    def open_videos(self, paths: Iterable[str]) -> list[str]:
        """
        Open video files and create sessions for each file.

        **Parameters:**

        - ``paths`` — Iterable of file path strings (e.g., list of absolute paths)

        **Returns:**

        List of successfully opened paths (excludes duplicates that were already open)

        **Behavior:**

        - Iterates through provided paths
        - Skips paths that are already open (``SessionAlreadyExistsException``)
        - Raises error if NO new sessions were opened
        - Sets first new session as active if none currently active

        **Error Handling:**

        - Raises ``NoNewOpenedSessionsException`` if all paths are duplicates
        - Logs info/warning for skipped paths, does not stop processing
        """
        # ====================================================================
        # 1. OPEN EACH VIDEO FROM PROVIDED PATHS
        # ====================================================================
        newly_opened: list[str] = []

        for path in paths:
            try:
                self._app_adapter.open_video_from_path(path)
                newly_opened.append(path)
            except SessionAlreadyExistsException:
                logger.info("Skipping already-open session '{}'", path)

        # ====================================================================
        # 2. VALIDATE AT LEAST ONE SESSION WAS OPENED
        # ====================================================================
        if len(newly_opened) == 0:
            raise NoNewOpenedSessionsException(0)

        # ====================================================================
        # 3. SET ACTIVE SESSION IF NONE IS ACTIVE
        # ====================================================================
        if not self._app_adapter.active_session_id:
            self._app_adapter.initialize_active_session()

        return newly_opened

    def session_by_id_has_buffered_frame(self, s_id: SessionId) -> bool:
        """
        Check if a pre-decoded frame is available in the buffer for the session.

        **Parameters:**

        - ``s_id`` — Session ID to check

        **Returns:**

        ``True`` if next frame is buffered and ready, ``False`` if buffer miss (worker behind)

        **Use Case:**

        During playback, check if the next frame is ready before rendering to avoid stutter.
        """
        return self._app_adapter.get_session_by_id(s_id).has_buffered_frame

    def session_by_id_has_running_detection_worker(self, s_id: SessionId) -> bool:
        """
        Check if a detection worker is currently running for the session.

        **Parameters:**

        - ``s_id`` — Session ID to check

        **Returns:**

        ``True`` if ``DetectionWorker`` exists and is actively running, ``False`` otherwise

        **Use Case:**

        Prevent starting another detection if one is already in progress.
        """
        return self._app_adapter.get_session_by_id(s_id).has_running_detection_worker

    def session_by_id_has_running_tracking_worker(self, s_id: SessionId) -> bool:
        """
        Check if a tracking worker is currently running for the session.

        **Parameters:**

        - ``s_id`` — Session ID to check

        **Returns:**

        ``True`` if ``TrackingWorker`` exists and is actively running, ``False`` otherwise

        **Use Case:**

        Prevent starting another tracking if one is already in progress.
        """
        return self._app_adapter.get_session_by_id(s_id).has_running_tracking_worker

    def update_session_settings(self, s_id: SessionId, **kwargs) -> None:
        """
        Update session settings by attribute name with type validation.

        **Parameters:**

        - ``s_id`` — Session ID
        - ``**kwargs`` — Keyword arguments where key is setting name, value is new value
          Examples: ``min_detection_confidence=0.5``, ``blur_enabled=True``, ``draw_boxes=False``

        **Behavior:**

        - Validates that the setting key exists; logs a warning and skips unknown keys.
        - Validates that the value type is compatible with the existing field type;
          logs a warning and skips type-mismatched updates.
        - ``int`` values are accepted for ``float`` fields (numeric widening).
        - Applies the update via ``setattr`` when all checks pass.

        **Example:**

        python
        service.update_session_settings(s_id, blur_strength=25, draw_boxes=True)
        
        """
        logger.info("Updating session settings for session ID: {}, settings={}  ", s_id, kwargs)
        session_settings = self._app_adapter.get_session_by_id(s_id).state.settings
        for key, value in kwargs.items():
            if not hasattr(session_settings, key):
                logger.warning(
                    "Unknown setting key '{}' while updating session settings, skipping...",
                    key,
                )
                continue
            existing_value = getattr(session_settings, key)
            if not _is_settings_type_compatible(existing_value, value):
                logger.warning(
                    "Type mismatch for setting '{}': expected {}, got {}, skipping...",
                    key,
                    type(existing_value).__name__,
                    type(value).__name__,
                )
                continue
            setattr(session_settings, key, value)
            # Trace after setattr so the log confirms the assignment succeeded.
            logger.trace("Session {} setting '{}' = {}", s_id, key, value)

    def start_session_playback(self, s_id: SessionId) -> None:
        self._app_adapter.get_session_by_id(s_id).is_playing_video = True
        logger.trace("Session {} playback started", s_id)
