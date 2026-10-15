"""Result processing collaborator for worker-produced tracking outputs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain import VideoDataLayer, new_passes_filter

if TYPE_CHECKING:
    from app.application.interfaces import UIApplicationInterface
    from app.domain.base.dtypes import ListOfBoxesByFrameIndexAsDict
    from app.domain.session import SessionId


class TrackingResultProcessor:
    """Refresh Layer C and replace Layer D machine boxes while preserving edits."""

    def __init__(self, session_repo: UIApplicationInterface) -> None:
        self._app_adapter = session_repo

    def overwrite_layer_c(
        self,
        s_id: SessionId,
        tracked_data: ListOfBoxesByFrameIndexAsDict,
    ) -> None:
        """Overwrite Layer C and refresh Layer D across the session frame range.

        Args:
            s_id: Session identifier receiving tracking results.
            tracked_data: Post-processed tracking boxes indexed by frame.

        Returns:
            None.

        Raises:
            Exception: Propagates invalid-session, filtering, and storage failures.

        Note:
            Layer D refresh is one bulk storage operation. Its existing manual
            boxes survive, while all machine boxes are re-filtered from Layer C.

        Example:
            processor.overwrite_layer_c(session_id, tracked_data)
        """
        session = self._app_adapter.get_session_by_id(s_id)
        session.data.overwrite_layer_with_dict_of_boxes(VideoDataLayer.C, tracked_data)
        session.data.replace_machine_boxes_for_frames(
            VideoDataLayer.D,
            tracked_data,
            session.state.metadata.frame_count,
            lambda box: new_passes_filter(VideoDataLayer.D, box, session.state.settings),
        )
