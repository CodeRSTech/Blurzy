"""
Module for model selection view model; defines application concepts without UI or infrastructure dependencies.

See Also:
    - [`get_detection_model_names_as_view_model_by_provider_id`][app.infrastructure.detection.model.helpers.get_detection_model_names_as_view_model_by_provider_id] — builds model choices by provider
    - [`ModelHandler`][app.ui.handlers.model_handler.ModelHandler] — applies model selection changes

Layer: Domain.
Context: Defines application concepts without ui or infrastructure dependencies at this architectural boundary.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ModelSelectionViewModel:
    """
    Dropdown item model for detection model selector (right panel).

    Attributes:
        model_id (str): Internal identifier used to load the model.
        display_name (str): User-facing label shown in the dropdown.
        provider_id (str): Stable provider/family identifier used for filtering.
        provider_display_name (str): User-facing provider label shown in provider pickers.

    Note:
        Instances flow from `DetectionService.get_available_detection_models()`
        to the UI dropdown, which displays `display_name` while keeping
        `model_id` available for the actual model selection.


    Layer: Domain.
    Context: Represents application concepts without UI or infrastructure dependencies.
    """

    model_id: str
    display_name: str
    provider_id: str = "all"
    provider_display_name: str = "All Models"
