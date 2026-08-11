"""Thin UI-layer facade over the concrete ``Application`` object."""

from __future__ import annotations

from typing import TYPE_CHECKING


from app.ui.interfaces.ui_application_interface import UIApplicationInterface
if TYPE_CHECKING:
    from typing import Unpack
    from app.domain import SessionId, VideoDataLayer


if TYPE_CHECKING:
    from app.application.application import Application
    from app.domain import ProcessingSettingsKwargs
    from app.infrastructure.session.session import Session


class UIApplicationAdapter(UIApplicationInterface):
    """Expose only the application surface currently needed by UI handlers."""

    def __init__(self, app: Application) -> None:
        self._app = app

    def __repr__(self) -> str:
        return f"<UIApplicationAdapter wrapping={self._app!r}>"

    @property
    def active_session(self) -> Session | None:
        return self._app.active_session

    @property
    def active_session_id(self) -> SessionId | None:
        return self._app.active_session_id

    @active_session_id.setter
    def active_session_id(self, s_id: SessionId) -> None:
        self._app.active_session_id = s_id

    def detect_current_frame(self, s_id: SessionId) -> None:
        self._app.detect_current_frame(s_id)

    def start_detection_worker(self, s_id: SessionId) -> None:
        self._app.start_detection_worker(s_id)

    def start_tracking_worker(
        self,
        s_id: SessionId,
        strategy_name: str,
        source_layer_name: VideoDataLayer,
    ) -> None:
        self._app.start_tracking_worker(s_id, strategy_name, source_layer_name)

    def get_session_by_id(self, s_id: SessionId) -> Session:
        return self._app.get_session_by_id(s_id)

    def update_session_settings(
        self,
        s_id: SessionId,
        **kwargs: Unpack[ProcessingSettingsKwargs],
    ) -> None:
        self._app.update_session_settings(s_id, **kwargs)

    def apply_filters_to_layer(self, layer_name: VideoDataLayer, s_id: SessionId) -> None:
        self._app.apply_filters_to_layer(layer_name=layer_name, s_id=s_id)

    def session_has_running_tracking_worker(self, s_id: SessionId) -> bool:
        return self._app.session_has_running_tracking_worker(s_id)

    def sync_tracking_cache(self, s_id: SessionId) -> None:
        self._app.sync_tracking_cache(s_id)

