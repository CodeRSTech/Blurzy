"""Unit tests for Session — bare constructor and explicit initialization contract."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

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


def test_constructor_creates_a_bare_session_shell():
    """Session construction should not open files or start workers anymore."""
    session = Session(SessionId("/videos/demo.mp4"))

    assert session.video_reader is None
    assert session.state is None
    assert session.video_decode_worker is None
    assert session.detection_engine is None
    assert session.detection_worker is None
    assert session.tracking_worker is None


def test_frame_access_before_initialization_raises_helpful_error():
    """Frame access should fail fast until SessionInitializer attaches runtime state."""
    session = Session(SessionId("/videos/demo.mp4"))

    with pytest.raises(RuntimeError, match="Session state has not been initialized yet"):
        session.get_current_frame()


def test_close_without_initialization_is_safe():
    """Closing a bare session should be a no-op for optional collaborators."""
    session = Session(SessionId("/videos/demo.mp4"))

    session.close()

