"""Export configuration — processing settings for detection, tracking, rendering.

See Also:
    - [`ProcessingSettings`][app.domain.export.processing_settings.ProcessingSettings] — settings record exposed by this package
    - [`SessionState`][app.domain.session.session_state.SessionState] — stores per-session processing options

Layer: Domain.
Context: Defines application concepts independently of UI and infrastructure implementations.
"""
from .processing_settings import ProcessingSettings

__all__ = ['ProcessingSettings',]