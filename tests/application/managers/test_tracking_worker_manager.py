"""Unit tests for TrackingWorkerManager lifecycle transitions."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.application.managers.tracking_worker import TrackingWorkerManager
from app.domain import ProcessingSettings, VideoDataLayer
from app.domain.detection import BoxSource
from app.domain.views import BBoxViewModel
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

    def test_start_seeds_uninitialized_layer_b_frames_from_filtered_layer_a(self):
        def box(box_id: str, confidence: float, label: str = "person") -> BBoxViewModel:
            return BBoxViewModel(
                id=box_id,
                source=BoxSource.DETECTION,
                label=label,
                bbox_xyxy=(0, 0, 10, 10),
                color_hex="#ffffff",
                confidence=confidence,
                key=box_id,
            )

        layer_a = {
            1: [box("accepted", 0.9), box("low-confidence", 0.2), box("wrong-label", 0.9, "cat")],
            2: [box("next-frame", 0.8)],
            3: [box("intentionally-removed", 0.8)],
        }
        edited = box("manual-edit", 0.7)
        layer_b = {2: [edited], 3: []}
        session = MagicMock()
        session.state.settings = ProcessingSettings(
            min_detection_confidence=0.5,
            chosen_labels=["person"],
        )
        session.get_layer_by_name.side_effect = (
            lambda layer: layer_a if layer == VideoDataLayer.A else layer_b
        )
        session.data.has_frame_for_layer_at_frame_index.side_effect = (
            lambda layer, frame_index: frame_index in layer_b
        )
        session.data.overwrite_layer_at_index_with_boxes.side_effect = (
            lambda layer, frame_index, boxes: layer_b.__setitem__(frame_index, boxes)
        )

        result = TrackingWorkerManager._get_supported_source_layer_data(
            session, MagicMock(), VideoDataLayer.B
        )

        assert result is layer_b
        assert [item.id for item in layer_b[1]] == ["accepted"]
        assert layer_b[1][0] is not layer_a[1][0]
        assert layer_b[2] == [edited]
        assert layer_b[3] == []

    @pytest.mark.parametrize("strategy_name", ["bytetrack", "deepsort"])
    def test_start_accepts_new_strategy_names(self, strategy_name: str):
        repo = MagicMock()
        source_data = {2: [MagicMock()]}
        session = _make_session(source_data=source_data)
        repo.get_session_by_id.return_value = session
        factory = MagicMock()
        created_worker = MagicMock()
        factory.create.return_value = created_worker
        manager = TrackingWorkerManager(repo, factory)

        manager.start(MagicMock(), strategy_name, VideoDataLayer.B)

        factory.create.assert_called_once_with(
            strategy_name=strategy_name,
            source_data=source_data,
            session_state=session.state,
        )
        assert session.tracking_worker is created_worker


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
