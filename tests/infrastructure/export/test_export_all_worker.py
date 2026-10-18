from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QObject, QThread, Qt, Slot

from app.domain import SessionId, VideoDataLayer
from app.infrastructure.adapters.export_all_worker_adapter import ExportAllWorkerAdapter
from app.infrastructure.export.export_all_worker import ExportAllWorker


def test_export_all_falls_back_to_layer_a_when_configured_layer_b_is_empty(tmp_path):
    s_id = MagicMock()
    s_id.basename_without_extension = "sample"
    session = MagicMock()
    session.state.settings.tracking_source = VideoDataLayer.B.value
    session.state.settings.tracking_strategy = "hungarian"
    session.has_boxes_for_layer.side_effect = lambda layer: layer == VideoDataLayer.A
    session.get_layer_by_name.return_value = {}
    session.has_running_tracking_worker = False

    app = MagicMock()
    app.sm.get_session_by_id.return_value = session
    app.session_is_ready_for_export.return_value = True
    worker = ExportAllWorker(app, [s_id], str(tmp_path), "pre_", "_post")

    assert worker._process_session(s_id)

    app.start_tracking_worker.assert_called_once_with(
        s_id, "hungarian", VideoDataLayer.A
    )
    app.sync_tracking_cache.assert_called_once_with(s_id)
    app.export_session.assert_called_once()


def test_export_all_does_not_fall_back_when_layer_b_has_initialized_empty_frames(tmp_path):
    s_id = MagicMock()
    s_id.basename_without_extension = "sample"
    session = MagicMock()
    session.state.settings.tracking_source = VideoDataLayer.B.value
    session.state.settings.tracking_strategy = "hungarian"
    session.has_boxes_for_layer.side_effect = lambda layer: layer == VideoDataLayer.A
    session.get_layer_by_name.return_value = {4: []}
    session.has_running_tracking_worker = False

    app = MagicMock()
    app.sm.get_session_by_id.return_value = session
    app.session_is_ready_for_export.return_value = True
    worker = ExportAllWorker(app, [s_id], str(tmp_path), "", "")

    assert worker._process_session(s_id)

    app.start_tracking_worker.assert_called_once_with(
        s_id, "hungarian", VideoDataLayer.B
    )


@pytest.mark.skipif(not isinstance(QObject, type), reason="Requires a real PySide6 installation")
def test_batch_signals_preserve_session_ids_through_queued_adapter_connections(qtbot, tmp_path):
    first = SessionId(str(tmp_path / "first" / "sample.mp4"))
    second = SessionId(str(tmp_path / "second" / "sample.mp4"))
    worker = ExportAllWorker(MagicMock(), [first, second], str(tmp_path), "", "")
    adapter = ExportAllWorkerAdapter(worker)
    events = []
    delivery_threads = []
    processing_threads = []

    class Receiver(QObject):
        def record(self, event):
            delivery_threads.append(QThread.currentThread())
            events.append(event)

        @Slot(object)
        def started(self, s_id):
            self.record(("started", s_id))

        @Slot(object)
        def finished(self, s_id):
            self.record(("finished", s_id))

        @Slot(object, str)
        def failed(self, s_id, error):
            self.record(("failed", s_id, error))

        @Slot(object, int, int)
        def frame_progress(self, s_id, current, total):
            self.record(("frame", s_id, current, total))

        @Slot(int, int)
        def progress(self, done, total):
            self.record(("progress", done, total))

        @Slot()
        def completed(self):
            self.record(("completed",))

    receiver = Receiver()
    for signal, slot in (
        (adapter.session_started, receiver.started),
        (adapter.session_finished, receiver.finished),
        (adapter.session_failed, receiver.failed),
        (adapter.session_export_progress_updated, receiver.frame_progress),
        (adapter.progress_updated, receiver.progress),
        (adapter.finished_processing, receiver.completed),
    ):
        signal.connect(slot, Qt.ConnectionType.QueuedConnection)

    def process_session(s_id):
        processing_threads.append(QThread.currentThread())
        worker._emit_export_progress_or_cancel(s_id, 3, 10)
        if s_id is second:
            raise RuntimeError("export failed")
        return True

    worker._process_session = MagicMock(side_effect=process_session)
    try:
        adapter.start()
        qtbot.waitUntil(lambda: bool(events) and events[-1] == ("completed",))
    finally:
        adapter.stop()
        assert worker.wait(5000)

    expected_events = [
        ("started", first),
        ("frame", first, 3, 10),
        ("finished", first),
        ("progress", 1, 2),
        ("started", second),
        ("frame", second, 3, 10),
        ("failed", second, "export failed"),
        ("progress", 2, 2),
        ("completed",),
    ]
    assert events == expected_events
    for event, expected in zip(events, expected_events, strict=True):
        if event[0] in {"started", "frame", "finished", "failed"}:
            assert isinstance(event[1], SessionId)
            assert event[1] is expected[1]
            assert event[1].basename == "sample.mp4"
    assert all(thread == receiver.thread() for thread in delivery_threads)
    assert processing_threads == [worker, worker]
