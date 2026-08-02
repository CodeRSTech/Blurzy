"""Unit tests for SessionInitializer — session bootstrap and worker startup."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

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

from app.application.managers.session_initializer import SessionInitializer
from app.domain.session import SessionId
from app.infrastructure.session.session import Session


def test_initialize_attaches_reader_state_and_worker():
    """SessionInitializer should attach all runtime collaborators in one step."""
    session = Session(SessionId("/videos/demo.mp4"))
    fake_reader = MagicMock(name="video_reader")
    fake_reader.metadata = MagicMock(name="metadata")
    fake_state = MagicMock(name="state")
    fake_state.playback = MagicMock(name="playback")
    fake_worker = MagicMock(name="decode_worker")

    with patch(
        "app.application.managers.session_initializer.VideoReader",
        return_value=fake_reader,
    ) as MockReader, patch(
        "app.application.managers.session_initializer.SessionState",
        return_value=fake_state,
    ) as MockState, patch(
        "app.application.managers.session_initializer.VideoDecodeWorker",
        return_value=fake_worker,
    ) as MockWorker:
        initializer = SessionInitializer()
        result = initializer.initialize(session)

    assert result is session
    MockReader.assert_called_once_with("/videos/demo.mp4")
    MockState.assert_called_once_with(session.s_id, fake_reader.metadata)
    MockWorker.assert_called_once_with(
        "/videos/demo.mp4",
        fake_state.playback,
        parent=session,
    )
    fake_worker.start.assert_called_once_with()
    assert session.video_reader is fake_reader
    assert session.state is fake_state
    assert session.video_decode_worker is fake_worker

