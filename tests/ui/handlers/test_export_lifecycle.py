"""Export outcome notifications must not dispose a running QThread."""

from threading import Event
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QObject

from app.domain import SessionId
from app.infrastructure.adapters.export_all_worker_adapter import ExportAllWorkerAdapter
from app.infrastructure.adapters.export_worker_adapter import ExportWorkerAdapter
from app.infrastructure.export.export_all_worker import ExportAllWorker
from app.infrastructure.export.export_worker import ExportCancelled, ExportWorker
from app.ui.handlers import export_handler as module
from app.ui.handlers.export_handler import ExportHandler


@pytest.mark.parametrize("adapter_type", [ExportWorkerAdapter, ExportAllWorkerAdapter])
def test_export_adapters_forward_shutdown_wait(adapter_type):
    worker = MagicMock()
    adapter_type(worker).wait()
    worker.wait.assert_called_once_with()


@pytest.mark.parametrize("batch", [False, True])
@pytest.mark.parametrize("outcome", ["success", "failure", "cancelled"])
def test_cleanup_waits_for_native_thread_finished(qtbot, monkeypatch, tmp_path, batch, outcome):
    processing_done = Event()
    allow_exit = Event()
    deleted_while_running = []
    s_id = SessionId(str(tmp_path / "sample.mp4"))
    owner = QObject()
    owner.window = MagicMock(selected_s_id=s_id)
    owner.app = MagicMock()
    owner.app.project_directories = SimpleNamespace(
        last_export_directory="", export_prefix="", export_suffix=""
    )
    owner.app.all_s_ids = [s_id]
    handler = ExportHandler(owner)
    handler._preferences_store.load = MagicMock(return_value=SimpleNamespace(
        default_export_prefix="", default_export_suffix="", default_export_directory=""
    ))

    if batch:
        class ControlledBatchWorker(ExportAllWorker):
            def run(self):
                super().run()
                processing_done.set()
                allow_exit.wait(5)

            def deleteLater(self):
                deleted_while_running.append(self.isRunning())
                super().deleteLater()

        worker = ControlledBatchWorker(owner.app, [s_id], str(tmp_path), "", "", parent=handler)
        if outcome == "failure":
            worker._process_session = MagicMock(side_effect=RuntimeError("test export failure"))
        elif outcome == "cancelled":
            worker.stop()
        else:
            worker._process_session = MagicMock(return_value=True)
        adapter = ExportAllWorkerAdapter(worker)
        handler._export_all_worker_factory.create = MagicMock(return_value=adapter)
        dialog = MagicMock()
        dialog.exec.return_value = 1
        dialog.get_export_config.return_value = (str(tmp_path), "", "")
        dialog_type = MagicMock(return_value=dialog)
        dialog_type.DialogCode.Accepted = 1
        monkeypatch.setattr(module, "ExportAllDialog", dialog_type)
        start = handler.on_export_all
    else:
        class ControlledWorker(ExportWorker):
            def run(self):
                super().run()
                processing_done.set()
                allow_exit.wait(5)

            def deleteLater(self):
                deleted_while_running.append(self.isRunning())
                super().deleteLater()

        service = MagicMock()
        if outcome == "failure":
            service.export_session.side_effect = RuntimeError("test export failure")
        elif outcome == "cancelled":
            service.export_session.side_effect = ExportCancelled
        worker = ControlledWorker(service, s_id, str(tmp_path / "out.mp4"), parent=handler)
        adapter = ExportWorkerAdapter(worker)
        handler._export_worker_factory.create = MagicMock(return_value=adapter)
        monkeypatch.setattr(module.QFileDialog, "getSaveFileName", lambda *args: (str(tmp_path / "out.mp4"), ""))
        start = handler.on_export

    try:
        start()
        qtbot.waitUntil(processing_done.is_set)
        qtbot.wait(20)
        assert worker.isRunning()
        assert handler.is_exporting
        assert not deleted_while_running
        owner.window.set_export_busy.assert_any_call(True, (
            "Batch exporting 1 video(s)..." if batch else "Exporting video..."
        ))
        assert not any(call.args == (False,) for call in owner.window.set_export_busy.call_args_list)
        allow_exit.set()
        qtbot.waitUntil(lambda: not handler.is_exporting)
        assert deleted_while_running == [False]
        owner.window.set_export_busy.assert_called_with(False)
    finally:
        allow_exit.set()
        if handler.is_exporting:
            handler.stop_exports(wait=True)
            qtbot.waitUntil(lambda: not handler.is_exporting)
