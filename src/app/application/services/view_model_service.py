"""Application-layer access to view models derived from domain state.

Layer: Application.
Context: Keeps UI-facing model preparation behind the application boundary,
using the application object as the source of session and domain data.
"""

class ViewModelService:
    """Provide application-backed view-model operations to presentation code."""

    def __init__(self, app):
        """Bind the service to the application that owns the relevant sessions.

        Args:
            app: Application facade used to access domain/session state.
        """
        self._app = app
