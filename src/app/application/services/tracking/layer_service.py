"""Tracking layer (Layer C/D) CRUD operations and track management."""

from __future__ import annotations

from typing import final, override, TYPE_CHECKING

from PySide6.QtCore import QObject

from app.application.adapters import ApplicationAdapter
from app.domain import VideoDataLayer
from app.domain.session import SessionId
from app.domain.video.direction import Direction
from app.shared.logging_cfg import get_logger

if TYPE_CHECKING:
    from app.application.application import Application

logger = get_logger("Application->TrackingLayerService")


@final
class TrackingLayerService(QObject):
    """
    Manages user-editable tracking layer (``DataLayer.D``) operations.

    Responsibilities:
        - CRUD operations for ``DataLayer.D`` tracked objects.
        - Copy tracks to adjacent frames.
        - Delete tracks by ID (removes across all frames matching ID).
        - Reset tracks (revert to ``DataLayer.C`` raw tracking output).
        - Track lifecycle management.

    Note:
        ``DataLayer.C`` — Raw immutable tracking output (machine-written).
        ``DataLayer.D`` — User-editable tracks (seeded from C, allows corrections).
        Tracks persist across frames (track ID unites multiple frame detections).
        User edits don't affect ``DataLayer.C`` (can always revert).

        Design pattern:
            Layer D is seeded Just-In-Time (lazy) from Layer C when accessed.
            User edits to Layer D are persistent (survives re-rendering).
            Layer C is immutable reference point.
    """

    def __init__(self, app: Application) -> None:
        super().__init__(parent=app)
        # self._app = app
        self._app_adapter = ApplicationAdapter(app)

    @override
    def __str__(self) -> str:
        return f"<{self.__class__.__name__}>"

    # CREATE
    # ================

    # READ
    # =====================

    # UPDATE
    # =====================

    # DELETE
    # =======================

    def delete_tracks_by_id_and_direction(self, s_id: SessionId, t_id: str, direction: Direction):
        # ============================================================
        # Get session
        # ============================================================
        session = self._app_adapter.get_session_by_id(s_id)

        if direction == Direction.NEXT:
            start = session.state.playback.current_frame_index + 1
            max_frame = max(session.state.metadata.frame_count - 1, 0)
            index_range = range(start, max_frame + 1)
        else:
            start = session.state.playback.current_frame_index - 1
            index_range = range(start, -1, -1)

        for frame_index in index_range:
            session.data.delete_boxes_from_layer_by_id_at_frame_index(VideoDataLayer.D, [t_id], frame_index)

    # def delete_tracker_all_occurrences(self, s_id: SessionId, t_id: str):
    #    self.delete_tracker_all_occurences(s_id, t_id)
