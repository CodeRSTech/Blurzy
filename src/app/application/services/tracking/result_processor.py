"""Result processing collaborator for worker-produced tracking outputs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain import VideoDataLayer

if TYPE_CHECKING:
    from app.application.interfaces import UIApplicationInterface
    from app.domain.base.dtypes import ListOfBoxesByFrameIndexAsDict
    from app.domain.session import SessionId


class TrackingResultProcessor:
    """Writes tracked output to Layer C while preserving existing semantics."""

    def __init__(self, session_repo: UIApplicationInterface) -> None:
        self._app_adapter = session_repo

    def overwrite_layer_c(
        self,
        s_id: SessionId,
        tracked_data: ListOfBoxesByFrameIndexAsDict,
    ) -> None:
        session = self._app_adapter.get_session_by_id(s_id)
        session.data.overwrite_layer_with_dict_of_boxes(VideoDataLayer.C, tracked_data)
