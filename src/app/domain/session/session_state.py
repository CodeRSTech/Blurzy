"""Session view_state management — playback, settings, and frame data.

See Also:
    - [`PlaybackState`][app.domain.video.playback_state.PlaybackState] — tracks the active frame and playback status
    - [`ProcessingSettings`][app.domain.export.processing_settings.ProcessingSettings] — stores per-session processing options

Layer: Domain.
Context: Defines application concepts independently of UI and infrastructure implementations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.domain.export.processing_settings import ProcessingSettings
from app.domain.video import PlaybackState
from app.shared.logging_cfg import get_logger

if TYPE_CHECKING:
    from app.domain.session import SessionId
    from app.domain.views import SessionSettingsViewModel
    from app.domain.video import VideoMetadata
    from app.infrastructure.dtypes import RGBFrame

logger = get_logger("Domain->Session")


@dataclass(slots=True)
class SessionState:
    """
    Manages runtime view_state for a single video processing session.

    Attributes:
        s_id (SessionId): Session identifier for the open video.
        metadata (VideoMetadata): Video file metadata such as size, FPS, and frame count.
        playback (PlaybackState): Current playback view_state for the session.
        settings (ProcessingSettings): User-configurable processing settings.
        current_frame_data (RGBFrame | None): Currently displayed RGB frame cache.
        next_annotation_id (int): Counter used for manual detection IDs.

    Note:
        This class is a runtime data container rather than a business-logic
        object. Bounding detection data lives separately in `SessionDataStore`,
        while playback, settings, and the current frame cache are kept here for
        fast UI access. Instances are created when a session opens, updated
        during playback and settings changes, and cleared when the session ends.


Layer: Domain.
Context: Represents application concepts without UI or infrastructure dependencies.
"""

    s_id: SessionId
    metadata: VideoMetadata

    playback: PlaybackState = field(default_factory=PlaybackState)
    settings: ProcessingSettings = field(default_factory=ProcessingSettings)
    current_frame_data: RGBFrame | None = field(default=None, repr=False)

    # [AUDIT] SRP VIOLATION: Annotation ID counter belongs elsewhere
    # SessionState mixing runtime view_state (playback, settings, frame data) with
    # domain-level counters (next_annotation_id). This conflates two concerns:
    # 1. Runtime playback/UI view_state (SessionState's job)
    # 2. Entity lifecycle management (AnnotationIdGenerator or SessionDataStore's job)
    # Recommendation: Move next_annotation_id to SessionDataStore or create separate
    # AnnotationIdSequence value object. SessionState should focus purely on playback/settings.
    next_annotation_id: int = 1

    @property
    def is_at_last_frame(self) -> bool:
        """Return whether playback is at or beyond the final video frame.

        Returns:
            `True` when no frames are reported or the current index reaches the last frame.
        """
        if self.metadata.frame_count <= 0:
            return True
        return self.playback.current_frame_index >= self.metadata.frame_count - 1

    @property
    def is_playing_video(self) -> bool:
        """Return whether video playback is active.

        Returns:
            `True` while playback is active; otherwise `False`.
        """
        return self.playback.is_playing

    @property
    def settings_view_model(self) -> SessionSettingsViewModel:
        """Return the session settings as a view model.

        Returns:
            View model built from the current processing settings.
        """
        return self.settings.as_view_model()

    def update_current_frame_data_and_index(self, idx: int, frame_data: RGBFrame) -> None:
        # [AUDIT] COMMAND QUERY SEPARATION & NAMING: Method name combines two concerns
        # 1. Update playback index (view_state change)
        # 2. Cache current frame data (presentation view_state)
        # Recommendation: Consider splitting into separate methods for clarity:
        # - set_playback_frame_index(idx) — updates position
        # - cache_frame_data(frame) — caches display data
        # This improves intent clarity and follows Single Responsibility Principle.
        """Update current frame data and index.

        Args:
            idx: Zero-based index of the displayed frame.
            frame_data: RGB pixel data for the displayed frame.
        """
        self.playback.current_frame_index = idx
        self.current_frame_data = frame_data
