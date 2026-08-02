"""Unit tests for SessionManager — session creation and bootstrap delegation."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from app.shared.exceptions import SessionAlreadyExistsException


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
    "app.application.managers.session",
):
    _module = sys.modules.get(_module_name)
    if _module is not None:
        importlib.reload(_module)

from app.application.managers.session import SessionManager
from app.domain.session import SessionId


def test_create_session_from_video_path_initializes_and_stores_session():
    """SessionManager should create a session and delegate runtime bootstrap."""
    app = MagicMock(name="app")
    initializer = MagicMock(name="initializer")
    initializer.initialize.side_effect = lambda session: session
    manager = SessionManager(app, session_initializer=initializer)

    path = "/videos/demo.mp4"
    manager.create_session_from_video_path(path)

    created_session = manager.get_session_by_id(SessionId(path))
    assert created_session.s_id == SessionId(path)
    initializer.initialize.assert_called_once_with(created_session)


def test_create_session_from_video_path_rejects_duplicates():
    """Duplicate video paths should raise before any new session is created."""
    app = MagicMock(name="app")
    initializer = MagicMock(name="initializer")
    manager = SessionManager(app, session_initializer=initializer)
    path = "/videos/demo.mp4"

    manager._sessions[SessionId(path)] = MagicMock(name="existing_session")

    with pytest.raises(SessionAlreadyExistsException):
        manager.create_session_from_video_path(path)

    initializer.initialize.assert_not_called()


def test_create_session_from_video_path_does_not_store_partial_session_on_failure():
    """If initialization fails, the new session should not be kept in the manager."""
    app = MagicMock(name="app")
    initializer = MagicMock(name="initializer")
    initializer.initialize.side_effect = RuntimeError("bootstrap failed")
    manager = SessionManager(app, session_initializer=initializer)

    with pytest.raises(RuntimeError, match="bootstrap failed"):
        manager.create_session_from_video_path("/videos/demo.mp4")

    assert list(manager.all_session_ids) == []

