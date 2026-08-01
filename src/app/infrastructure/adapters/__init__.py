"""Infrastructure-layer adapters — explicit wrappers to application interface contracts.

Each adapter wraps a concrete infrastructure class and exposes the corresponding
application-layer interface.  Concrete classes already satisfy their Protocol
interfaces via structural subtyping; these adapters provide explicit named seams
for documentation and testing purposes.
"""

from app.infrastructure.adapters.detection_engine_adapter import DetectionEngineAdapter
from app.infrastructure.adapters.detection_worker_adapter import DetectionWorkerAdapter
from app.infrastructure.adapters.export_all_worker_adapter import ExportAllWorkerAdapter
from app.infrastructure.adapters.export_worker_adapter import ExportWorkerAdapter
from app.infrastructure.adapters.video_decode_worker_control_adapter import VideoDecodeWorkerControlAdapter

__all__ = [
    "DetectionEngineAdapter",
    "DetectionWorkerAdapter",
    "ExportAllWorkerAdapter",
    "ExportWorkerAdapter",
    "VideoDecodeWorkerControlAdapter",
]
