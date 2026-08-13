"""Centralizes video decode worker activation and deactivation per session."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.shared.logging_cfg import get_logger

if TYPE_CHECKING:
    from app.application.interfaces import UIApplicationInterface
    from app.domain.session import SessionId

logger = get_logger("Application->VideoDecodeWorkerManager")


class VideoDecodeWorkerManager:
    """
    Manages ``VideoDecodeWorker`` activation and deactivation on a per-session basis.

    Responsibilities:
        - Activate a session's decode worker (start buffering frames from the
          current playback position).
        - Deactivate a session's decode worker (stop buffering, free memory).

    This manager centralises the worker-toggle logic that previously lived
    inside ``SessionService._activate_video_decode_worker_for_session_id``
    and ``SessionService._deactivate_video_decode_worker_for_session_id``,
    giving ``SessionService`` a narrower single responsibility.

    ``ValueError`` exceptions from ``set_active()`` are intentionally swallowed
    here to preserve the original silent-return behaviour: they indicate that
    the worker is in a transient view_state (e.g. not yet started) where the
    toggle cannot be applied.

    The session repository is injected, so the manager is independently
    unit-testable without a live ``Application`` instance.
    """

    def __init__(self, session_repo: UIApplicationInterface) -> None:
        self._app_adapter = session_repo

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"

    def activate(self, s_id: SessionId) -> None:
        """
        Resume the video decode worker for ``s_id`` (start buffering frames).

        Seeks to the session's current playback position so the ring buffer
        is filled with the frames the user is about to see.

        Args:
            s_id: Session ID of the target session.

        Note:
            Silently returns if the worker raises ``ValueError`` (transient
            worker view_state — mirrors the original ``SessionService`` behaviour).
        """
        logger.trace("Waking up session {} worker.", s_id)
        session = self._app_adapter.get_session_by_id(s_id)
        try:
            session.video_decode_worker.set_active(
                active=True, resume_idx=session.state.playback.current_frame_index
            )
        except ValueError as exc:
            logger.warning(
                "Decode worker for session {} could not be activated due to transient worker view_state: {}",
                s_id,
                exc,
            )
            return

    def deactivate(self, s_id: SessionId) -> None:
        """
        Pause the video decode worker for ``s_id`` (stop buffering, free RAM).

        Clears the ring buffer immediately to reclaim the memory used by
        pre-decoded frames.

        Args:
            s_id: Session ID of the target session.

        Note:
            Silently returns if the worker raises ``ValueError`` (transient
            worker view_state — mirrors the original ``SessionService`` behaviour).
        """
        logger.debug("Putting session {} to sleep.", s_id)
        session = self._app_adapter.get_session_by_id(s_id)
        try:
            session.video_decode_worker.set_active(active=False)
        except ValueError as exc:
            logger.warning(
                "Decode worker for session {} could not be deactivated due to transient worker view_state: {}",
                s_id,
                exc,
            )
            return

    def switch_active_session(
        self, old_s_id: SessionId | None, new_s_id: SessionId
    ) -> None:
        """
        Perform the canonical old→new active-session decode-worker transition.

        Pauses the old session's decode worker (if any) then resumes the new
        one.  The method is a no-op when ``old_s_id == new_s_id`` so that
        callers do not need to guard against redundant switches themselves.

        Args:
            old_s_id: Previously active session ID, or ``None`` on first open.
            new_s_id: Newly active session ID.

        Note:
            Individual ``activate`` / ``deactivate`` calls preserve their
            existing ``ValueError`` tolerance semantics.
        """
        if old_s_id is not None and old_s_id == new_s_id:
            logger.trace(
                "switch_active_session: old and new are the same ({}), skipping.",
                new_s_id,
            )
            return

        if old_s_id is not None:
            self.deactivate(old_s_id)

        self.activate(new_s_id)
