from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ModelSelectionViewModel:
    """
    Dropdown item model for detection model selector (right panel).

    Attributes:
        model_id (str): Internal identifier used to load the model.
        display_name (str): User-facing label shown in the dropdown.

    Note:
        Instances flow from ``DetectionService.get_available_detection_models()``
        to the UI dropdown, which displays ``display_name`` while keeping
        ``model_id`` available for the actual model selection.
    """

    model_id: str
    display_name: str
