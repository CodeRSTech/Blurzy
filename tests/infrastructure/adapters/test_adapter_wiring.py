"""Tests for adapter/interface/factory wiring correctness.

Validates that:
- Each adapter explicitly inherits from its corresponding interface.
- The DetectionEngineFactory produces DetectionEngineAdapter-wrapped engines (Pattern B).
- Adapters correctly delegate calls to their wrapped concrete implementations.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.application.interfaces import (
    DetectionEngineFactoryInterface,
    DetectionEngineInterface,
    DetectionWorkerInterface,
    ExportAllWorkerFactoryInterface,
    ExportAllWorkerInterface,
    ExportWorkerFactoryInterface,
    ExportWorkerInterface,
    TrackingWorkerFactoryInterface,
    VideoDecodeWorkerControlInterface,
)
from app.infrastructure.adapters.detection_engine_adapter import DetectionEngineAdapter
from app.infrastructure.adapters.detection_worker_adapter import DetectionWorkerAdapter
from app.infrastructure.adapters.export_all_worker_adapter import ExportAllWorkerAdapter
from app.infrastructure.adapters.export_worker_adapter import ExportWorkerAdapter
from app.infrastructure.adapters.video_decode_worker_control_adapter import VideoDecodeWorkerControlAdapter
from app.application.adapters.export_all_worker_factory_adapter import ExportAllWorkerFactoryAdapter
from app.application.adapters.export_worker_factory_adapter import ExportWorkerFactoryAdapter
from app.application.adapters.tracking_worker_factory_adapter import TrackingWorkerFactoryAdapter


# ---------------------------------------------------------------------------
# Interface conformance — adapters must inherit from their interface
# ---------------------------------------------------------------------------

class TestAdapterInterfaceInheritance:
    """Each adapter must declare explicit inheritance from its interface."""

    def test_detection_engine_adapter_inherits_interface(self):
        assert DetectionEngineInterface in DetectionEngineAdapter.__mro__

    def test_detection_worker_adapter_inherits_interface(self):
        assert DetectionWorkerInterface in DetectionWorkerAdapter.__mro__

    def test_video_decode_worker_control_adapter_inherits_interface(self):
        assert VideoDecodeWorkerControlInterface in VideoDecodeWorkerControlAdapter.__mro__

    def test_tracking_worker_factory_adapter_inherits_interface(self):
        assert TrackingWorkerFactoryInterface in TrackingWorkerFactoryAdapter.__mro__

    def test_export_worker_adapter_inherits_interface(self):
        assert ExportWorkerInterface in ExportWorkerAdapter.__mro__

    def test_export_all_worker_adapter_inherits_interface(self):
        assert ExportAllWorkerInterface in ExportAllWorkerAdapter.__mro__

    def test_export_worker_factory_adapter_inherits_interface(self):
        assert ExportWorkerFactoryInterface in ExportWorkerFactoryAdapter.__mro__

    def test_export_all_worker_factory_adapter_inherits_interface(self):
        assert ExportAllWorkerFactoryInterface in ExportAllWorkerFactoryAdapter.__mro__


# ---------------------------------------------------------------------------
# DetectionEngineFactory — must produce DetectionEngineAdapter-wrapped engines
# ---------------------------------------------------------------------------

class TestDetectionEngineFactoryWiring:
    """DetectionEngineFactory.create() must return a DetectionEngineAdapter (Pattern B)."""

    def test_factory_returns_adapter_not_raw_engine(self):
        from app.infrastructure.detection.engine.detection_engine_factory import DetectionEngineAdapterFactory

        fake_engine = MagicMock(name="FakeDetectionEngine")
        with patch(
            "app.infrastructure.detection.engine.detection_engine.DetectionEngine",
            return_value=fake_engine,
        ):
            factory = DetectionEngineAdapterFactory()
            result = factory.create("YOLOv8n")

        assert isinstance(result, DetectionEngineAdapter), (
            "DetectionEngineFactory.create() must return a DetectionEngineAdapter, "
            "not a raw DetectionEngine — ensure Pattern B wiring is in place."
        )

    def test_factory_adapter_wraps_correct_engine(self):
        from app.infrastructure.detection.engine.detection_engine_factory import DetectionEngineAdapterFactory

        fake_engine = MagicMock(name="FakeDetectionEngine")
        with patch(
                "app.infrastructure.detection.engine.detection_engine_factory.DetectionEngine",
                return_value=fake_engine,
        ):
            factory = DetectionEngineAdapterFactory()
            result = factory.create("YOLOv8n")

        assert result._engine is fake_engine

    def test_factory_satisfies_factory_interface(self):
        from app.infrastructure.detection.engine.detection_engine_factory import DetectionEngineAdapterFactory

        assert DetectionEngineFactoryInterface in DetectionEngineAdapterFactory.__mro__


# ---------------------------------------------------------------------------
# DetectionEngineAdapter — delegate correctness
# ---------------------------------------------------------------------------

class TestDetectionEngineAdapterDelegation:
    """DetectionEngineAdapter must delegate all interface calls to the wrapped engine."""

    def _make_adapter(self):
        fake_engine = MagicMock()
        fake_engine.model_name = "YOLOv8n"
        return DetectionEngineAdapter(fake_engine), fake_engine

    def test_model_name_property_delegates(self):
        adapter, engine = self._make_adapter()
        assert adapter.model_name == "YOLOv8n"

    def test_set_model_delegates(self):
        adapter, engine = self._make_adapter()
        adapter.set_model("yolov8s")
        engine.set_model.assert_called_once_with("yolov8s")

    def test_detect_delegates(self):
        adapter, engine = self._make_adapter()
        fake_frame = MagicMock(name="frame")
        fake_results = [MagicMock()]
        engine.detect.return_value = fake_results

        result = adapter.detect(fake_frame)

        engine.detect.assert_called_once_with(fake_frame)
        assert result is fake_results


# ---------------------------------------------------------------------------
# DetectionWorkerAdapter — delegate correctness
# ---------------------------------------------------------------------------

class TestDetectionWorkerAdapterDelegation:
    """DetectionWorkerAdapter must delegate all interface calls to the wrapped worker."""

    def _make_adapter(self):
        fake_worker = MagicMock()
        return DetectionWorkerAdapter(fake_worker), fake_worker

    def test_start_delegates(self):
        adapter, worker = self._make_adapter()
        adapter.start()
        worker.start.assert_called_once()

    def test_stop_delegates(self):
        adapter, worker = self._make_adapter()
        adapter.stop()
        worker.stop.assert_called_once()

    def test_isRunning_delegates(self):
        adapter, worker = self._make_adapter()
        worker.isRunning.return_value = True
        assert adapter.isRunning() is True

    def test_is_complete_delegates(self):
        adapter, worker = self._make_adapter()
        worker.is_complete.return_value = False
        assert adapter.is_complete() is False

    def test_get_detections_delegates(self):
        adapter, worker = self._make_adapter()
        fake_results = [MagicMock()]
        worker.get_detections.return_value = fake_results
        assert adapter.get_detections(42) is fake_results
        worker.get_detections.assert_called_once_with(42)

    def test_get_all_detections_delegates(self):
        adapter, worker = self._make_adapter()
        fake_data = {0: [], 1: [MagicMock()]}
        worker.get_all_detections.return_value = fake_data
        assert adapter.get_all_detections() is fake_data


# ---------------------------------------------------------------------------
# VideoDecodeWorkerControlAdapter — delegate correctness
# ---------------------------------------------------------------------------

class TestVideoDecodeWorkerControlAdapterDelegation:
    """VideoDecodeWorkerControlAdapter must delegate all interface calls to the wrapped worker."""

    def _make_adapter(self):
        fake_worker = MagicMock()
        return VideoDecodeWorkerControlAdapter(fake_worker), fake_worker

    def test_set_active_true_delegates(self):
        adapter, worker = self._make_adapter()
        adapter.set_active(True, resume_idx=10)
        worker.set_active.assert_called_once_with(active=True, resume_idx=10)

    def test_set_active_false_delegates(self):
        adapter, worker = self._make_adapter()
        adapter.set_active(False)
        worker.set_active.assert_called_once_with(active=False, resume_idx=0)

    def test_stop_delegates(self):
        adapter, worker = self._make_adapter()
        adapter.stop()
        worker.stop.assert_called_once()

    def test_get_cached_frame_at_index_delegates(self):
        adapter, worker = self._make_adapter()
        fake_frame = MagicMock(name="frame")
        worker.get_cached_frame_at_index.return_value = fake_frame
        result = adapter.get_cached_frame_at_index(5)
        assert result is fake_frame
        worker.get_cached_frame_at_index.assert_called_once_with(5)


class TestExportWorkerAdapterDelegation:
    def _make_adapter(self):
        fake_worker = MagicMock()
        fake_worker.progress_updated = MagicMock()
        fake_worker.succeeded = MagicMock()
        fake_worker.finished_processing = MagicMock()
        fake_worker.cancelled = MagicMock()
        fake_worker.error_occurred = MagicMock()
        return ExportWorkerAdapter(fake_worker), fake_worker

    def test_signals_are_exposed(self):
        adapter, worker = self._make_adapter()
        assert adapter.progress_updated is worker.progress_updated
        assert adapter.succeeded is worker.succeeded
        assert adapter.finished_processing is worker.finished_processing
        assert adapter.cancelled is worker.cancelled
        assert adapter.error_occurred is worker.error_occurred

    def test_start_stop_isrunning_delete_later_delegate(self):
        adapter, worker = self._make_adapter()
        worker.isRunning.return_value = True

        adapter.start()
        adapter.stop()
        running = adapter.isRunning()
        adapter.deleteLater()

        worker.start.assert_called_once_with()
        worker.stop.assert_called_once_with()
        worker.isRunning.assert_called_once_with()
        worker.deleteLater.assert_called_once_with()
        assert running is True


class TestExportAllWorkerAdapterDelegation:
    def _make_adapter(self):
        fake_worker = MagicMock()
        fake_worker.session_started = MagicMock()
        fake_worker.session_finished = MagicMock()
        fake_worker.session_failed = MagicMock()
        fake_worker.progress_updated = MagicMock()
        fake_worker.session_export_progress_updated = MagicMock()
        fake_worker.finished_processing = MagicMock()
        fake_worker.cancelled = MagicMock()
        return ExportAllWorkerAdapter(fake_worker), fake_worker

    def test_signals_are_exposed(self):
        adapter, worker = self._make_adapter()
        assert adapter.session_started is worker.session_started
        assert adapter.session_finished is worker.session_finished
        assert adapter.session_failed is worker.session_failed
        assert adapter.progress_updated is worker.progress_updated
        assert adapter.session_export_progress_updated is worker.session_export_progress_updated
        assert adapter.finished_processing is worker.finished_processing
        assert adapter.cancelled is worker.cancelled

    def test_start_stop_isrunning_delete_later_delegate(self):
        adapter, worker = self._make_adapter()
        worker.isRunning.return_value = False

        adapter.start()
        adapter.stop()
        running = adapter.isRunning()
        adapter.deleteLater()

        worker.start.assert_called_once_with()
        worker.stop.assert_called_once_with()
        worker.isRunning.assert_called_once_with()
        worker.deleteLater.assert_called_once_with()
        assert running is False


class TestExportFactoryAdapterWiring:
    def test_export_worker_factory_returns_adapter(self):
        factory = ExportWorkerFactoryAdapter()
        fake_export_service = MagicMock()
        fake_session_id = MagicMock()
        fake_worker = MagicMock()

        with patch("app.infrastructure.export.ExportWorker", return_value=fake_worker):
            result = factory.create(
                export_service=fake_export_service,
                s_id=fake_session_id,
                output_path="output.mp4",
            )

        assert isinstance(result, ExportWorkerAdapter)
        assert result._worker is fake_worker

    def test_export_all_worker_factory_returns_adapter(self):
        factory = ExportAllWorkerFactoryAdapter()
        fake_app = MagicMock()
        fake_ids = [MagicMock()]
        fake_worker = MagicMock()

        with patch("app.infrastructure.export.ExportAllWorker", return_value=fake_worker):
            result = factory.create(
                app=fake_app,
                s_ids=fake_ids,
                output_dir="output",
                prefix="pre_",
                suffix="_suf",
            )

        assert isinstance(result, ExportAllWorkerAdapter)
        assert result._worker is fake_worker
