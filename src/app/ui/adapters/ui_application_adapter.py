"""Thin UI-layer facade over the concrete `Application` object.

See Also:
    - [`UIApplicationInterface`][app.ui.interfaces.ui_application_interface.UIApplicationInterface] — defines the UI-facing application contract
    - [`Application`][app.application.application.Application] — concrete application wrapped by the adapter

Layer: Presentation.
Context: Bridges UI-facing contracts to application operations.
"""

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
    """Expose only the application surface currently needed by UI handlers.

Layer: Presentation.
Context: Supports user interaction and delegates application work through presentation contracts.


    Args:
        app: Concrete application whose session, detection, tracking, and settings methods are delegated.
"""

    def __init__(self, app: Application) -> None:
        self._app = app

    def __repr__(self) -> str:
        return f"<UIApplicationAdapter wrapping={self._app!r}>"

    @property
    def active_session(self) -> Session | None:
        """Return the currently active session, if any.

        Returns:
            Active session object, or `None` when no session is active.
        """
        return self._app.active_session

    @property
    def active_session_id(self) -> SessionId | None:
        """Return the active session identifier, if any.

        Returns:
            Active session identifier, or `None` when no session is active.
        """
        return self._app.active_session_id

    @active_session_id.setter
    def active_session_id(self, s_id: SessionId) -> None:
        """Set the active session identifier through the application facade.

        Args:
            s_id: Identifier of the session to activate.
        """
        self._app.active_session_id = s_id

    def detect_current_frame(self, s_id: SessionId) -> None:
        """Run detection on the session's current video frame.

        Args:
            s_id: Identifier of the session to process.
        """
        self._app.detect_current_frame(s_id)

    def start_detection_worker(self, s_id: SessionId) -> None:
        """Start background detection for all frames in a session.

        Args:
            s_id: Identifier of the session to process.
        """
        self._app.start_detection_worker(s_id)

    def start_tracking_worker(
        self,
        s_id: SessionId,
        strategy_name: str,
        source_layer_name: VideoDataLayer,
    ) -> None:
        """Start background tracking for a session using a selected source layer.

        Args:
            s_id: Identifier of the session to track.
            strategy_name: Tracking strategy to run.
            source_layer_name: Detection layer supplying the tracking input.
        """
        self._app.start_tracking_worker(s_id, strategy_name, source_layer_name)

    def get_session_by_id(self, s_id: SessionId) -> Session:
        """Return the session identified by `s_id`.

        Args:
            s_id: Identifier of the session to retrieve.

        Returns:
            Matching infrastructure session.
        """
        return self._app.get_session_by_id(s_id)

    def update_session_settings(
        self,
        s_id: SessionId,
        **kwargs: Unpack[ProcessingSettingsKwargs],
    ) -> None:
        """Update processing settings for a session.

        Args:
            s_id: Identifier of the session to update.
            kwargs: Setting names and replacement values accepted by `ProcessingSettings`.
        """
        self._app.update_session_settings(s_id, **kwargs)

    def apply_filters_to_layer(self, layer_name: VideoDataLayer, s_id: SessionId) -> None:
        """Reapply confidence and size filters to an editable detection or tracking layer.

        Args:
            layer_name: Editable layer B or D to filter.
            s_id: Identifier of the session whose layer is updated.
        """
        self._app.apply_filters_to_layer(layer_name=layer_name, s_id=s_id)

    def session_has_running_tracking_worker(self, s_id: SessionId) -> bool:
        """Check whether a session's tracking worker is active.

        Args:
            s_id: Identifier of the session to check.

        Returns:
            `True` when its tracking worker is running.
        """
        return self._app.session_has_running_tracking_worker(s_id)

    def sync_tracking_cache(self, s_id: SessionId) -> None:
        """Synchronize completed tracking results into the session's tracking layers.

        Args:
            s_id: Identifier of the session whose tracking results are synchronized.

        Side Effects:
            Replaces immutable layer C and seeds uninitialized layer D frames while preserving edits.
        """
        self._app.sync_tracking_cache(s_id)
