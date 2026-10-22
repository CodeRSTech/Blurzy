"""Package for detection; implements use cases by coordinating domain and infrastructure operations.

See Also:
    - [`DetectionService`][app.application.services.detection.service.DetectionService] — orchestrates model-based detection
    - [`DetectionBatchProcessor`][app.application.services.detection.batch_processor.DetectionBatchProcessor] — processes worker results

Layer: Application.
Context: Implements use cases by coordinating domain and infrastructure operations at this architectural boundary.
"""

from .exporting import DetectionExportService
from .importing import DetectionImportService
from .layer import DetectionLayerService
from .service import DetectionService

__all__ = [
    'DetectionService',
    'DetectionLayerService',
    'DetectionImportService',
    'DetectionExportService',
]
