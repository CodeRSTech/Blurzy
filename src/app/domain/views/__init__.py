"""
View model for UI binding — boxes, sessions, settings, model selection.

See Also:
    - [`ViewModelService`][app.application.services.view_model_service.ViewModelService] — prepares domain view models for presentation
    - [`BottomDataPanelContainer`][app.ui.qt.sections.bottom_data_panel.BottomDataPanelContainer] — displays session and box view models

Layer: Domain.
Context: Defines application concepts independently of UI and infrastructure implementations.
"""

from .bounding_box_view_model import BBoxViewModel
from .frame_boxes_view_model import FrameBoxesViewModel
from .session_file_list_view_model import SessionFileListViewModel
from .session_settings_view_model import SessionSettingsViewModel
from .model_selection_view_model import ModelSelectionViewModel

__all__ = [
    "SessionFileListViewModel",
    "BBoxViewModel",
    "FrameBoxesViewModel",
    "ModelSelectionViewModel",
    "SessionSettingsViewModel",
]