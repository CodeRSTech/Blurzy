"""
UI-owned application facade contract consumed by UI handlers.

This protocol lives in the UI layer on purpose: it describes the subset of the
concrete `Application` facade that UI handlers need. It is *not* a duplicate
of the application-layer service contracts; it is the UI's view of the app.

See Also:
    - [`Application`][app.application.application.Application] — supplies the underlying workflows
    - [`UIApplicationAdapter`][app.ui.adapters.ui_application_adapter.UIApplicationAdapter] — adapts the application for UI handlers


Layer: Presentation.
Context: Defines presentation-facing contracts for controllers, application access, and windows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol
if TYPE_CHECKING:
    from typing import Unpack
    from app.domain import SessionId, VideoDataLayer



if TYPE_CHECKING:
    from app.domain import ProcessingSettingsKwargs
    from app.infrastructure.session.session import Session as InfraSession


class UIApplicationInterface(Protocol):
    """
    Narrow application facade exposed to UI handlers.

    Layer: Presentation.
    Context: Supports user interaction and delegates application work through presentation contracts.
    """

    @property
    def active_session(self) -> InfraSession | None:
        """
        Return the currently active session, if any.

        Returns:
            Active session object, or `None` when no session is active.
        """
        ...

    @property
    def active_session_id(self) -> SessionId | None:
        """
        Return the active session identifier, if any.

        Returns:
            Active session identifier, or `None` when no session is active.
        """
        ...

    @active_session_id.setter
    def active_session_id(self, s_id: SessionId) -> None:
        """
        Set the active session identifier.

        Args:
            s_id: Identifier of the session to activate.
        """
        ...

    def detect_current_frame(self, s_id: SessionId) -> None:
        """
        Run detection on the session's current video frame.

        Args:
            s_id: Identifier of the session to process.
        """
        ...

    def start_detection_worker(self, s_id: SessionId) -> None:
        """
        Start background detection for all frames in a session.

        Args:
            s_id: Identifier of the session to process.
        """
        ...

    def get_detection_frame_coverage(self, s_id: SessionId) -> tuple[int, int]:
        """Return processed detection-frame count and video length.

        Args:
            s_id: Session to inspect before tracking.
        """
        ...

    def start_tracking_worker(
        self,
        s_id: SessionId,
        strategy_name: str,
        source_layer_name: VideoDataLayer,
    ) -> None:
        """
        Start background tracking for a session using a selected source layer.

        Args:
            s_id: Identifier of the session to track.
            strategy_name: Tracking strategy to run.
            source_layer_name: Detection layer supplying the tracking input.
        """
        ...

    def get_session_by_id(self, s_id: SessionId) -> InfraSession:
        """
        Return the session identified by `s_id`.

        Args:
            s_id: Identifier of the session to retrieve.

        Returns:
            Matching infrastructure session.
        """
        ...

    def update_session_settings(
        self,
        s_id: SessionId,
        **kwargs: Unpack[ProcessingSettingsKwargs],
    ) -> None:
        """
        Update processing settings for a session.

        Args:
            s_id: Identifier of the session to update.
            kwargs: Setting names and replacement values accepted by `ProcessingSettings`.
        """
        ...

    def apply_filters_to_layer(self, layer_name: VideoDataLayer, s_id: SessionId) -> None:
        """
        Reapply confidence and size filters to an editable detection or tracking layer.

        Args:
            layer_name: Editable layer B or D to filter.
            s_id: Identifier of the session whose layer is updated.
        """
        ...

    def session_has_running_tracking_worker(self, s_id: SessionId) -> bool:
        """
        Check whether a session's tracking worker is active.

        Args:
            s_id: Identifier of the session to check.

        Returns:
            `True` when its tracking worker is running.
        """
        ...

    def sync_tracking_cache(self, s_id: SessionId) -> None:
        """
        Synchronize completed tracking results into the session's tracking layers.

        Args:
            s_id: Identifier of the session whose tracking results are synchronized.

        Side Effects:
            Replaces immutable layer C and seeds uninitialized layer D frames while preserving edits.
        """
        ...
