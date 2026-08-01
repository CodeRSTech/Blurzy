"""Unit tests for Session runtime worker-state properties."""

from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock

import pytest


class _QObjectStub:
    def __init__(self, *args, **kwargs):
        pass


@pytest.fixture
def session_cls(monkeypatch):
    qtcore_module = sys.modules.get("PySide6.QtCore")
    if qtcore_module is not None:
        monkeypatch.setattr(qtcore_module, "QObject", _QObjectStub)

    session_module = importlib.import_module("app.infrastructure.session.session")
    return importlib.reload(session_module).Session


def _make_session(session_cls):
    return session_cls.__new__(session_cls)


class TestHasRunningDetectionWorker:
    def test_false_when_worker_missing(self, session_cls):
        session = _make_session(session_cls)
        session.detection_worker = None

        assert session.has_running_detection_worker is False

    def test_delegates_to_worker_interface(self, session_cls):
        session = _make_session(session_cls)
        worker = MagicMock()
        worker.isRunning.return_value = True
        session.detection_worker = worker

        assert session.has_running_detection_worker is True
        worker.isRunning.assert_called_once_with()


class TestHasRunningTrackingWorker:
    def test_false_when_worker_missing(self, session_cls):
        session = _make_session(session_cls)
        session.tracking_worker = None

        assert session.has_running_tracking_worker is False

    def test_delegates_to_worker_interface(self, session_cls):
        session = _make_session(session_cls)
        worker = MagicMock()
        worker.isRunning.return_value = True
        session.tracking_worker = worker

        assert session.has_running_tracking_worker is True
        worker.isRunning.assert_called_once_with()
