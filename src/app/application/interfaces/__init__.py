"""Application-layer interface contracts (Phase 1 abstraction seams).

These ``Protocol``-based interfaces decouple services and managers from
concrete infrastructure implementations.  Concrete classes satisfy them
via structural subtyping — no explicit ``implements`` declaration is required.
"""

from app.application.interfaces.detection.engine_factory_interface import DetectionEngineFactoryInterface
from app.application.interfaces.detection.engine_interface import DetectionEngineInterface
from app.application.interfaces.detection.worker_factory_interface import DetectionWorkerFactoryInterface
from app.application.interfaces.detection.worker_interface import DetectionWorkerInterface

from app.application.interfaces.export_all.worker_factory_interface import ExportAllWorkerFactoryInterface
from app.application.interfaces.export_all.worker_interface import ExportAllWorkerInterface
from app.application.interfaces.export.factory_interface import ExportWorkerFactoryInterface
from app.application.interfaces.export.worker_interface import ExportWorkerInterface

from app.application.interfaces.session.session_data_store_interface import SessionDataStoreInterface
from app.application.interfaces.application_interface import UIApplicationInterface

from app.application.interfaces.tracking.worker_factory_interface import TrackingWorkerFactoryInterface
from app.application.interfaces.tracking.worker_interface import TrackingWorkerInterface

from app.application.interfaces.video.decode_worker_control_interface import VideoDecodeWorkerControlInterface
from app.application.interfaces.data_import_interface import IDataImporter
from app.application.interfaces.data_export_interface import IDataExporter

__all__ = [
    "DetectionEngineFactoryInterface",
    "DetectionEngineInterface",
    "DetectionWorkerInterface",
    "DetectionWorkerFactoryInterface",
    "ExportAllWorkerFactoryInterface",
    "ExportAllWorkerInterface",
    "ExportWorkerFactoryInterface",
    "ExportWorkerInterface",
    "TrackingWorkerInterface",
    "TrackingWorkerFactoryInterface",
    "VideoDecodeWorkerControlInterface",
    "UIApplicationInterface",
    "SessionDataStoreInterface",
    "IDataImporter",
    "IDataExporter",
]
