"""Module for engine factory interface; defines contracts independent of concrete adapters.

See Also:
    - [`DetectionEngineAdapterFactory`][app.infrastructure.detection.engine.detection_engine_factory.DetectionEngineAdapterFactory] — implements engine construction
    - [`DetectionEngineManager`][app.application.managers.detection_engine.DetectionEngineManager] — consumes the factory contract

Layer: Application.
Context: Defines contracts independent of concrete adapters at this architectural boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


from typing import Protocol
if TYPE_CHECKING:
    from app.application.interfaces.detection.engine_interface import DetectionEngineInterface



class DetectionEngineFactoryInterface(Protocol):
    """
    The `DetectionEngineFactoryInterface`

    `DetectionEngineFactory` in `Infrastructure/detection` is instantiated from it,

    which is then used by the `DetectionEngineManager`.


Layer: Application.
Context: Coordinates use-case behavior through domain services and application contracts.
"""
    def create(self, model_name: str) -> DetectionEngineInterface:
        """Create a detection engine configured for the requested model.

        Args:
            model_name: Registry name of the detection model.

        Returns:
            Engine implementing `DetectionEngineInterface`.
        """
        ...