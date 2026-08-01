"""Unit tests for VideoDecodeWorkerManager — activate / deactivate semantics."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.application.managers.video_decode_worker import VideoDecodeWorkerManager


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_session_repo(current_frame_index: int = 0, worker_raises: Exception | None = None):
    """
    Return a mock SessionRepositoryInterface whose session has a mock worker.

    Args:
        current_frame_index: The value of ``session.state.playback.current_frame_index``.
        worker_raises: If set, ``set_active`` will raise this exception.
    """
    worker = MagicMock()
    if worker_raises is not None:
        worker.set_active.side_effect = worker_raises

    session = MagicMock()
    session.video_decode_worker = worker
    session.state.playback.current_frame_index = current_frame_index

    repo = MagicMock()
    repo.get_session_by_id.return_value = session
    return repo, session, worker


# ---------------------------------------------------------------------------
# activate — normal path
# ---------------------------------------------------------------------------

class TestActivate:
    """activate() should call set_active(True, resume_idx=<current_frame_index>)."""

    def test_calls_set_active_true_with_current_index(self):
        repo, session, worker = _make_session_repo(current_frame_index=42)
        manager = VideoDecodeWorkerManager(repo)
        s_id = MagicMock()

        manager.activate(s_id)

        worker.set_active.assert_called_once_with(active=True, resume_idx=42)

    def test_uses_current_playback_frame_index(self):
        repo, session, worker = _make_session_repo(current_frame_index=100)
        manager = VideoDecodeWorkerManager(repo)
        s_id = MagicMock()

        manager.activate(s_id)

        _, kwargs = worker.set_active.call_args
        assert kwargs["resume_idx"] == 100

    def test_fetches_session_by_id(self):
        repo, session, worker = _make_session_repo()
        manager = VideoDecodeWorkerManager(repo)
        s_id = MagicMock()

        manager.activate(s_id)

        repo.get_session_by_id.assert_called_once_with(s_id)


# ---------------------------------------------------------------------------
# activate — ValueError handling (mirrors original SessionService behaviour)
# ---------------------------------------------------------------------------

class TestActivateValueError:
    """activate() must silently return when set_active raises ValueError."""

    def test_silently_returns_on_value_error(self):
        repo, session, worker = _make_session_repo(worker_raises=ValueError("transient state"))
        manager = VideoDecodeWorkerManager(repo)
        s_id = MagicMock()

        # Should NOT raise
        manager.activate(s_id)

    def test_does_not_propagate_value_error(self):
        repo, session, worker = _make_session_repo(worker_raises=ValueError("boom"))
        manager = VideoDecodeWorkerManager(repo)
        s_id = MagicMock()

        try:
            manager.activate(s_id)
        except ValueError:
            pytest.fail("activate() propagated a ValueError — expected silent return")


# ---------------------------------------------------------------------------
# deactivate — normal path
# ---------------------------------------------------------------------------

class TestDeactivate:
    """deactivate() should call set_active(False) with no resume_idx."""

    def test_calls_set_active_false(self):
        repo, session, worker = _make_session_repo()
        manager = VideoDecodeWorkerManager(repo)
        s_id = MagicMock()

        manager.deactivate(s_id)

        worker.set_active.assert_called_once_with(active=False)

    def test_does_not_pass_resume_idx(self):
        repo, session, worker = _make_session_repo()
        manager = VideoDecodeWorkerManager(repo)
        s_id = MagicMock()

        manager.deactivate(s_id)

        _, kwargs = worker.set_active.call_args
        assert "resume_idx" not in kwargs

    def test_fetches_session_by_id(self):
        repo, session, worker = _make_session_repo()
        manager = VideoDecodeWorkerManager(repo)
        s_id = MagicMock()

        manager.deactivate(s_id)

        repo.get_session_by_id.assert_called_once_with(s_id)


# ---------------------------------------------------------------------------
# deactivate — ValueError handling
# ---------------------------------------------------------------------------

class TestDeactivateValueError:
    """deactivate() must silently return when set_active raises ValueError."""

    def test_silently_returns_on_value_error(self):
        repo, session, worker = _make_session_repo(worker_raises=ValueError("transient state"))
        manager = VideoDecodeWorkerManager(repo)
        s_id = MagicMock()

        # Should NOT raise
        manager.deactivate(s_id)

    def test_does_not_propagate_value_error(self):
        repo, session, worker = _make_session_repo(worker_raises=ValueError("boom"))
        manager = VideoDecodeWorkerManager(repo)
        s_id = MagicMock()

        try:
            manager.deactivate(s_id)
        except ValueError:
            pytest.fail("deactivate() propagated a ValueError — expected silent return")


# ---------------------------------------------------------------------------
# Parity check: manager activates with same args as the old SessionService code
# ---------------------------------------------------------------------------

class TestParityWithOldSessionService:
    """
    Verify that the manager reproduces the exact call signature that
    the old ``SessionService`` private methods used before Phase 1.
    """

    def test_activate_parity(self):
        """Parity: set_active(active=True, resume_idx=current_frame_index)."""
        current_idx = 77
        repo, session, worker = _make_session_repo(current_frame_index=current_idx)
        manager = VideoDecodeWorkerManager(repo)
        s_id = MagicMock()

        manager.activate(s_id)

        worker.set_active.assert_called_once_with(active=True, resume_idx=current_idx)

    def test_deactivate_parity(self):
        """Parity: set_active(active=False) — no resume_idx."""
        repo, session, worker = _make_session_repo()
        manager = VideoDecodeWorkerManager(repo)
        s_id = MagicMock()

        manager.deactivate(s_id)

        worker.set_active.assert_called_once_with(active=False)


# ---------------------------------------------------------------------------
# switch_active_session — canonical old→new transition (Phase 3)
# ---------------------------------------------------------------------------

class TestSwitchActiveSession:
    """switch_active_session() must implement the canonical old→new transition."""

    def test_deactivates_old_then_activates_new(self):
        """Old session deactivated before new session activated, in that order."""
        old_id = MagicMock(name="old")
        new_id = MagicMock(name="new")

        repo = MagicMock()
        old_session, new_session = MagicMock(), MagicMock()
        repo.get_session_by_id.side_effect = lambda s: (
            old_session if s is old_id else new_session
        )
        old_session.state.playback.current_frame_index = 0
        new_session.state.playback.current_frame_index = 10

        manager = VideoDecodeWorkerManager(repo)
        call_order = []
        old_session.video_decode_worker.set_active.side_effect = (
            lambda **kw: call_order.append(("deactivate", kw))
        )
        new_session.video_decode_worker.set_active.side_effect = (
            lambda **kw: call_order.append(("activate", kw))
        )

        manager.switch_active_session(old_s_id=old_id, new_s_id=new_id)

        assert call_order[0] == ("deactivate", {"active": False})
        assert call_order[1] == ("activate", {"active": True, "resume_idx": 10})

    def test_only_activates_new_when_old_is_none(self):
        """With no prior session (first open), only activate new."""
        repo, session, worker = _make_session_repo(current_frame_index=5)
        manager = VideoDecodeWorkerManager(repo)
        new_id = MagicMock()

        manager.switch_active_session(old_s_id=None, new_s_id=new_id)

        worker.set_active.assert_called_once_with(active=True, resume_idx=5)

    def test_no_op_when_old_equals_new(self):
        """Switching to the same session must not touch any worker."""
        repo = MagicMock()
        manager = VideoDecodeWorkerManager(repo)
        same_id = MagicMock()

        manager.switch_active_session(old_s_id=same_id, new_s_id=same_id)

        repo.get_session_by_id.assert_not_called()

    def test_deactivate_value_error_does_not_prevent_activate(self):
        """Even if deactivating old session raises ValueError, new session is activated."""
        old_id = MagicMock(name="old")
        new_id = MagicMock(name="new")

        repo = MagicMock()
        old_session, new_session = MagicMock(), MagicMock()
        repo.get_session_by_id.side_effect = lambda s: (
            old_session if s is old_id else new_session
        )
        old_session.video_decode_worker.set_active.side_effect = ValueError("transient")
        new_session.state.playback.current_frame_index = 0

        manager = VideoDecodeWorkerManager(repo)

        # Must not raise, and must still activate the new session
        manager.switch_active_session(old_s_id=old_id, new_s_id=new_id)

        new_session.video_decode_worker.set_active.assert_called_once_with(
            active=True, resume_idx=0
        )

    def test_activate_value_error_is_tolerated(self):
        """ValueError from activating new session is swallowed (same parity as activate())."""
        repo, session, worker = _make_session_repo(worker_raises=ValueError("boom"))
        manager = VideoDecodeWorkerManager(repo)

        # Should NOT raise
        manager.switch_active_session(old_s_id=None, new_s_id=MagicMock())


# ---------------------------------------------------------------------------
# Regression: switch_active_session parity with old SessionService behaviour
# ---------------------------------------------------------------------------

class TestSwitchActiveSessionRegressionParity:
    """
    Regression tests confirming switch_active_session reproduces the exact
    call sequence from the old ``SessionService.handle_active_session_changed``
    before Phase 3 delegation.

    Old code (before Phase 3)::

        if old_s_id:
            self._deactivate_video_decode_worker_for_session_id(old_s_id)
        self._activate_video_decode_worker_for_session_id(new_s_id)

    Each private call ultimately called ``set_active(active=False)`` and
    ``set_active(active=True, resume_idx=current_frame_index)`` respectively.
    """

    def test_full_switch_call_signature_parity(self):
        """set_active calls must match the original per-session worker toggle."""
        old_id = MagicMock(name="old")
        new_id = MagicMock(name="new")

        repo = MagicMock()
        old_session, new_session = MagicMock(), MagicMock()
        repo.get_session_by_id.side_effect = lambda s: (
            old_session if s is old_id else new_session
        )
        new_session.state.playback.current_frame_index = 42

        manager = VideoDecodeWorkerManager(repo)
        manager.switch_active_session(old_s_id=old_id, new_s_id=new_id)

        old_session.video_decode_worker.set_active.assert_called_once_with(active=False)
        new_session.video_decode_worker.set_active.assert_called_once_with(
            active=True, resume_idx=42
        )


