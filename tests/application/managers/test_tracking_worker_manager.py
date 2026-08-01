"""Unit tests for TrackingWorkerManager lifecycle transitions."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.application.managers.tracking_worker import TrackingWorkerManager
from app.domain import VideoDataLayer
from app.shared.exceptions import (
    EmptyLayerException,
    TrackingWorkerAlreadyRunningException,
    UnsupportedLayerException,
)


def _make_session(*, running: bool = False, source_data: dict | None = None):
    session = MagicMock()
    session.has_running_tracking_worker = running
    session.get_layer_by_name.return_value = source_data if source_data is not None else {1: []}
    session.tracking_worker = None
    return session


class TestStart:
    def test_start_creates_worker_and_clears_layers(self):
        repo = MagicMock()
        source_data = {2: [MagicMock()]}
        session = _make_session(source_data=source_data)
        repo.get_session_by_id.return_value = session
        factory = MagicMock()
        created_worker = MagicMock()
        factory.create.return_value = created_worker
        manager = TrackingWorkerManager(repo, factory)

        manager.start(MagicMock(), "hungarian", VideoDataLayer.B)

        session.data.clear_layers_by_name.assert_called_once_with([VideoDataLayer.C, VideoDataLayer.D])
        factory.create.assert_called_once_with(
            strategy_name="hungarian",
            source_data=source_data,
            session_state=session.state,
        )
        assert session.tracking_worker is created_worker

    def test_start_raises_when_worker_already_running(self):
        repo = MagicMock()
        repo.get_session_by_id.return_value = _make_session(running=True)
        manager = TrackingWorkerManager(repo, MagicMock())

        with pytest.raises(TrackingWorkerAlreadyRunningException):
            manager.start(MagicMock(), "hungarian", VideoDataLayer.A)

    def test_start_raises_for_unsupported_source_layer(self):
        repo = MagicMock()
        repo.get_session_by_id.return_value = _make_session()
        manager = TrackingWorkerManager(repo, MagicMock())

        with pytest.raises(UnsupportedLayerException):
            manager.start(MagicMock(), "hungarian", VideoDataLayer.C)

    def test_start_raises_for_empty_source_layer(self):
        repo = MagicMock()
        repo.get_session_by_id.return_value = _make_session(source_data={})
        manager = TrackingWorkerManager(repo, MagicMock())

        with pytest.raises(EmptyLayerException):
            manager.start(MagicMock(), "hungarian", VideoDataLayer.A)


class TestStop:
    def test_stop_calls_worker_stop_and_clears_reference(self):
        repo = MagicMock()
        session = _make_session()
        worker = MagicMock()
        session.tracking_worker = worker
        repo.get_session_by_id.return_value = session
        manager = TrackingWorkerManager(repo, MagicMock())

        manager.stop(MagicMock())

        worker.stop.assert_called_once_with()
        assert session.tracking_worker is None

    def test_stop_is_noop_when_worker_missing(self):
        repo = MagicMock()
        session = _make_session()
        session.tracking_worker = None
        repo.get_session_by_id.return_value = session
        manager = TrackingWorkerManager(repo, MagicMock())

        manager.stop(MagicMock())

        repo.get_session_by_id.assert_called_once()

    def test_stop_tolerates_value_error(self):
        repo = MagicMock()
        session = _make_session()
        worker = MagicMock()
        worker.stop.side_effect = ValueError("transient")
        session.tracking_worker = worker
        repo.get_session_by_id.return_value = session
        manager = TrackingWorkerManager(repo, MagicMock())

        manager.stop(MagicMock())


class TestSwitchActiveSession:
    def test_switch_stops_old_then_starts_new(self):
        old_id = MagicMock(name="old")
        new_id = MagicMock(name="new")
        old_session = _make_session()
        new_session = _make_session(source_data={3: [MagicMock()]})

        repo = MagicMock()
        repo.get_session_by_id.side_effect = lambda s: old_session if s is old_id else new_session
        factory = MagicMock()
        new_worker = MagicMock()
        factory.create.return_value = new_worker
        old_worker = MagicMock()
        old_session.tracking_worker = old_worker

        manager = TrackingWorkerManager(repo, factory)
        manager.switch_active_session(old_id, new_id, "hungarian", VideoDataLayer.B)

        old_worker.stop.assert_called_once_with()
        assert old_session.tracking_worker is None
        assert new_session.tracking_worker is new_worker

    def test_switch_noop_when_old_equals_new(self):
        repo = MagicMock()
        factory = MagicMock()
        manager = TrackingWorkerManager(repo, factory)
        same_id = MagicMock()

        manager.switch_active_session(same_id, same_id, "hungarian", VideoDataLayer.A)

        repo.get_session_by_id.assert_not_called()
        factory.create.assert_not_called()
