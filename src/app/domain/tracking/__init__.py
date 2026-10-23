"""
Tracking configuration — tracking strategy enumeration.

See Also:
    - [`TrackingStrategy`][app.domain.tracking.tracking_strategy.TrackingStrategy] — selectable tracking algorithms
    - [`TrackingService`][app.application.services.tracking.service.TrackingService] — executes tracking workflows

Layer: Domain.
Context: Defines application concepts independently of UI and infrastructure implementations.
"""
from .tracking_strategy import TrackingStrategy

__all__ = ["TrackingStrategy"]