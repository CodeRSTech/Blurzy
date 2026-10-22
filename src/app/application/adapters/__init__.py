"""Application-layer adapters — explicit wrappers for application interface contracts.

These adapters wrap higher-level application objects (e.g. `Application`) to expose
narrow interface contracts consumed by services and managers.

See Also:
    - [`ApplicationAdapter`][app.application.adapters.application_adapter.ApplicationAdapter] — wraps the application facade
    - [`TrackingWorkerFactoryAdapter`][app.application.adapters.tracking_worker_factory_adapter.TrackingWorkerFactoryAdapter] — creates tracking workers behind a contract


Layer: Application.
Context: Adapts infrastructure implementations to application contracts.
"""

from app.application.adapters.application_adapter import ApplicationAdapter
from app.application.adapters.export_all_worker_factory_adapter import ExportAllWorkerFactoryAdapter
from app.application.adapters.export_worker_factory_adapter import ExportWorkerFactoryAdapter
from app.application.adapters.tracking_worker_factory_adapter import TrackingWorkerFactoryAdapter

__all__ = [
    "ApplicationAdapter",
    "ExportAllWorkerFactoryAdapter",
    "ExportWorkerFactoryAdapter",
    "TrackingWorkerFactoryAdapter",
]
