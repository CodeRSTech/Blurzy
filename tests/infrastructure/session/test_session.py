"""Unit tests for Session — bare constructor and explicit initialization contract."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))


class _QObjectStub:
    """Minimal real QObject replacement for unit tests."""

    def __init__(self, *args, **kwargs):
        pass


_qtcore_module = sys.modules.get("PySide6.QtCore")
if _qtcore_module is not None:
    _qtcore_module.QObject = _QObjectStub

for _module_name in (
    "app.infrastructure.session.session",
    "app.application.managers.session_initializer",
):
    _module = sys.modules.get(_module_name)
    if _module is not None:
        importlib.reload(_module)

from app.domain.session import SessionId
from app.infrastructure.session.session import Session


def _make_session(path: str = "/videos/demo.mp4") -> Session:
    """Create Session with SessionDataStore patched for QObject-free unit testing."""
    with patch("app.infrastructure.session.session.SessionDataStore", return_value=MagicMock(name="data_store")):
        return Session(SessionId(path))


def test_constructor_creates_a_bare_session_shell():
    """Session construction should not open files or start workers anymore."""
    session = _make_session()

    assert session.video_reader is None
    assert session.state is None
    assert session.video_decode_worker is None
    assert session.detection_engine is None
    assert session.detection_worker is None
    assert session.tracking_worker is None


def test_frame_access_before_initialization_raises_helpful_error():
    """Frame access should fail fast until SessionInitializer attaches runtime view_state."""
    session = _make_session()

    with pytest.raises(RuntimeError, match="Session view_state has not been initialized yet"):
        session.get_current_frame()


def test_close_without_initialization_is_safe():
    """Closing a bare session should be a no-op for optional collaborators."""
    session = _make_session()

    session.close()


def test_get_frame_by_index_delegates_to_frame_accessor():
    """Session should delegate frame orchestration to its dedicated accessor."""
    session = _make_session()
    fake_state = MagicMock(name="view_state")
    fake_worker = MagicMock(name="worker")
    session.state = fake_state
    session.video_decode_worker = fake_worker
    session._frame_accessor = MagicMock(name="frame_accessor")
    session._frame_accessor.get_frame_by_index.return_value = "delegated-frame"

    result = session.get_frame_by_index(12)

    assert result == "delegated-frame"
    session._frame_accessor.get_frame_by_index.assert_called_once_with(
        session_state=fake_state,
        decode_worker=fake_worker,
        frame_index=12,
    )


def test_frame_navigation_helpers_delegate_to_frame_accessor():
    """Session frame helpers should stay as thin wrappers over frame accessor."""
    session = _make_session()
    fake_state = MagicMock(name="view_state")
    fake_state.playback.current_frame_index = 5
    fake_worker = MagicMock(name="worker")
    session.state = fake_state
    session.video_decode_worker = fake_worker
    session._frame_accessor = MagicMock(name="frame_accessor")

    session._frame_accessor.get_current_frame.return_value = "current"
    session._frame_accessor.get_next_frame.return_value = "next"
    session._frame_accessor.get_previous_frame.return_value = "prev"
    session._frame_accessor.get_buffered_frame.return_value = "buffered"

    assert session.get_current_frame() == "current"
    assert session.get_next_frame() == "next"
    assert session.get_previous_frame() == "prev"
    assert session.get_buffered_frame() == "buffered"

    session._frame_accessor.get_current_frame.assert_called_once_with(
        session_state=fake_state,
        decode_worker=fake_worker,
    )
    session._frame_accessor.get_next_frame.assert_called_once_with(
        session_state=fake_state,
        decode_worker=fake_worker,
    )
    session._frame_accessor.get_previous_frame.assert_called_once_with(
        session_state=fake_state,
        decode_worker=fake_worker,
    )
    session._frame_accessor.get_buffered_frame.assert_called_once_with(
        session_state=fake_state,
        decode_worker=fake_worker,
    )


