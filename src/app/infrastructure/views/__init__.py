"""View model factories for converting domain objects to UI representations.

See Also:
    - [`list_of_session_list_view_models`][app.infrastructure.views.view_models.list_of_session_list_view_models] — builds session-list entries
    - [`SessionHandler`][app.ui.handlers.session_handler.SessionHandler] — presents session lists in the UI

Layer: Infrastructure.
Context: Implements concrete processing and I/O behind application-facing contracts.
"""
from .view_models import list_of_session_list_view_models

__all__ = ['list_of_session_list_view_models']