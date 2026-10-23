"""
Session domain model — session ID, view_state, playback, data layer selection.

See Also:
    - [`Session`][app.infrastructure.session.session.Session] — infrastructure container for runtime session state
    - [`SessionInitializer`][app.application.managers.session_initializer.SessionInitializer] — initializes session collaborators

Layer: Domain.
Context: Defines application concepts independently of UI and infrastructure implementations.
"""

from .session_id import SessionId
from .session_state import SessionState

__all__ = [
    'SessionState',
    'SessionId',]