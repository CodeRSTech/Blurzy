"""
Application-layer access to view models derived from domain state.

See Also:
    - [`BBoxViewModel`][app.domain.views.bounding_box_view_model.BBoxViewModel] — domain view model prepared for the UI
    - [`FrameBoxesViewModel`][app.domain.views.frame_boxes_view_model.FrameBoxesViewModel] — groups box view models for a frame

Layer: Application.
Context: Keeps UI-facing model preparation behind the application boundary,
using the application object as the source of session and domain data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.application import Application


class ViewModelService:
    """
    Provide application-backed view-model operations to presentation code.

    Layer: Application.
    Context: Coordinates use-case behavior through domain services and application contracts.
    """

    def __init__(self, app: Application):
        """
        Bind the service to the application that owns the relevant sessions.

        Args:
            app: Application facade used to access domain/session state.
        """
        self._app = app
