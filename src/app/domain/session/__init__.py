"""Session domain model — session ID, view_state, playback, data layer selection.

Layer: Domain.
Context: Defines application concepts independently of UI and infrastructure implementations.
"""

from .session_id import SessionId
from .session_state import SessionState

__all__ = [
    'SessionState',
    'SessionId',]