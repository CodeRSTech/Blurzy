"""UI-owned application facade contract consumed by UI handlers.

This protocol lives in the UI layer on purpose: it describes the subset of the
concrete ``Application`` facade that UI handlers need. It is *not* a duplicate
of the application-layer service contracts; it is the UI's view of the app.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Unpack

from app.domain import SessionId, VideoDataLayer

if TYPE_CHECKING:
    from app.domain import ProcessingSettingsKwargs
    from app.infrastructure.session.session import Session as InfraSession


class UIApplicationInterface(Protocol):
    """Narrow application facade exposed to UI handlers."""

    @property
    def active_session(self) -> InfraSession | None:
        ...

    @property
    def active_session_id(self) -> SessionId | None:
        ...

    @active_session_id.setter
    def active_session_id(self, s_id: SessionId) -> None:
        ...

    def detect_current_frame(self, s_id: SessionId) -> None:
        ...

    def start_detection_worker(self, s_id: SessionId) -> None:
        ...

    def start_tracking_worker(
        self,
        s_id: SessionId,
        strategy_name: str,
        source_layer_name: VideoDataLayer,
    ) -> None:
        ...

    def get_session_by_id(self, s_id: SessionId) -> InfraSession:
        ...

    def update_session_settings(
        self,
        s_id: SessionId,
        **kwargs: Unpack[ProcessingSettingsKwargs],
    ) -> None:
        ...

    def apply_filters_to_layer(self, layer_name: VideoDataLayer, s_id: SessionId) -> None:
        ...

    def session_has_running_tracking_worker(self, s_id: SessionId) -> bool:
        ...

    def sync_tracking_cache(self, s_id: SessionId) -> None:
        ...



