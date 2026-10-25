"""
Tracking layer (Layer C/D) CRUD operations and track management.

See Also:
    - [`Direction`][app.domain.video.direction.Direction] — selects the direction for track propagation
    - [`UnifiedLayerService`][app.application.services.unified_layer_service.UnifiedLayerService] — coordinates operations across layers

Layer: Application.
Context: Coordinates domain state and infrastructure to complete application use cases.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final, override

from PySide6.QtCore import QObject

from app.application.adapters import ApplicationAdapter
from app.application.services.helpers.layer_seeding import seed_layer_frame_from_layer
from app.domain import VideoDataLayer

from app.domain.video.direction import Direction
from app.shared.logging_cfg import get_logger
from app.shared.exceptions import UnsupportedDirectionException
if TYPE_CHECKING:
    from app.domain.session import SessionId


if TYPE_CHECKING:
    from app.application.application import Application

logger = get_logger("Application->TrackingLayerService")


@final
class TrackingLayerService(QObject):
    """
    Manages user-editable tracking layer (`DataLayer.D`) operations.

    Responsibilities:
        - CRUD operations for `DataLayer.D` tracked objects.
        - Copy tracks to adjacent frames.
        - Delete tracks by ID (removes across all frames matching ID).
        - Reset tracks (revert to `DataLayer.C` raw tracking output).
        - Track lifecycle management.

    Note:
        `DataLayer.C` — Post-processed immutable tracking output (machine-written).
        `DataLayer.D` — User-editable tracks seeded from C, allowing corrections.
        Tracks persist across frames (track ID unites multiple frame detections).
        User edits don't affect `DataLayer.C` (can always revert).

        Design pattern:
            New tracking output eagerly seeds Layer D; older sessions retain JIT seeding.
            User edits to Layer D are persistent (survives re-rendering).
            Layer C is immutable reference point.



    Args:
        app: Application adapted for session lookup and tracking-layer reads and mutations.
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

    def delete_tracks_by_id_and_direction(self, s_id: SessionId, t_id: str, direction: Direction) -> None:
        """
        Delete a track's later or earlier occurrences in reviewed Layer D.

        Args:
            s_id: Identifier of the session whose tracks are edited.
            t_id: Track identifier to delete from subsequent or preceding frames.
            direction: Whether to delete forward from or backward before the current frame.

        Raises:
            UnsupportedDirectionException: If direction is neither NEXT nor PREV.

        Side Effects:
            Seeds absent D frames from C using the same filters as tab reads.
            Resolves display IDs to storage keys before deletion. Current frame,
            initialized edits, and immutable C remain intact; empty D entries
            prevent deleted tracks from being re-seeded on subsequent reads.
        """
        session = self._app_adapter.get_session_by_id(s_id)

        if direction == Direction.NEXT:
            start = session.state.playback.current_frame_index + 1
            max_frame = max(session.state.metadata.frame_count - 1, 0)
            index_range = range(start, max_frame + 1)
        elif direction == Direction.PREV:
            start = session.state.playback.current_frame_index - 1
            index_range = range(start, -1, -1)
        else:
            raise UnsupportedDirectionException(direction)

        changed_frames = 0
        for frame_index in index_range:
            with session.data.data_lock:
                seed_layer_frame_from_layer(VideoDataLayer.C, VideoDataLayer.D, session, frame_index)
                boxes = session.data.get_boxes_for_layer_at_frame_index_as_list(VideoDataLayer.D, frame_index)
                keys = [box.key for box in boxes if box.id == t_id]
                changed_frames += session.data.delete_boxes_from_layer_by_id_at_frame_index(
                    VideoDataLayer.D, keys, frame_index
                )
        logger.info("Deleted track '{}' in {} {} frames for session '{}'", t_id, changed_frames, direction, s_id)
