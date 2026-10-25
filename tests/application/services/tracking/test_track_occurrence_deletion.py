"""Directional deletion must edit D keys and never resurrect tracks from C."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QObject

from app.application.services.tracking.layer_service import TrackingLayerService
from app.application.services.unified_layer_service import UnifiedLayerService
from app.domain import Direction, ProcessingSettings, VideoDataLayer, VideoDataLayerGroup
from app.domain.detection import BoxSource
from app.domain.views import BBoxViewModel
from app.infrastructure.session.session_data_store import SessionDataStore
from app.shared.exceptions import UnsupportedDirectionException


def _track(track_id: str) -> BBoxViewModel:
    return BBoxViewModel(
        id=track_id, key=f"track:{track_id}", source=BoxSource.TRACKING_HUNGARIAN,
        label="person", bbox_xyxy=(10, 10, 30, 30), color_hex="#00ff00", confidence=0.9,
    )


@pytest.mark.parametrize("direction,affected", [(Direction.NEXT, {3, 4}), (Direction.PREV, {0, 1})])
@pytest.mark.parametrize("initialized", [False, True])
def test_directional_deletion_resolves_ids_and_preserves_reviewed_empty_frames(direction, affected, initialized):
    store = SessionDataStore(s_id="video")
    for index in range(5):
        store.overwrite_layer_at_index_with_boxes(VideoDataLayer.C, index, [_track("-4"), _track("-5")])
        if initialized:
            store.overwrite_layer_at_index_with_boxes(VideoDataLayer.D, index, [_track("-4"), _track("-5")])
    # A previous explicit review must not be re-seeded while deleting another track.
    store.overwrite_layer_at_index_with_boxes(VideoDataLayer.D, 0, [])
    session = SimpleNamespace(
        data=store,
        state=SimpleNamespace(
            playback=SimpleNamespace(current_frame_index=2),
            metadata=SimpleNamespace(frame_count=5),
            settings=ProcessingSettings(),
        ),
    )
    repo = MagicMock()
    repo.get_session_by_id.return_value = session
    service = TrackingLayerService.__new__(TrackingLayerService)
    QObject.__init__(service)
    service._app_adapter = repo
    tabs = UnifiedLayerService.__new__(UnifiedLayerService)
    tabs._app_adapter = repo

    # Reading the selected frame seeds D for older C-only projects.
    tabs.get_tab_frame_boxes_for_session_id("video", VideoDataLayerGroup.TRACKING)
    service.delete_tracks_by_id_and_direction("video", "-4", direction)

    for index in range(5):
        session.state.playback.current_frame_index = index
        boxes = tabs.get_tab_frame_boxes_for_session_id("video", VideoDataLayerGroup.TRACKING).frame_data_boxes
        expected = [] if index == 0 else (["-5"] if index in affected else ["-4", "-5"])
        assert [box.id for box in boxes] == expected
        assert [box.id for box in store.get_boxes_for_layer_at_frame_index_as_list(VideoDataLayer.C, index)] == [
            "-4", "-5"
        ]

    # Removing the final remaining track must leave a persistent empty D entry.
    session.state.playback.current_frame_index = 2
    service.delete_tracks_by_id_and_direction("video", "-5", direction)
    for index in affected:
        session.state.playback.current_frame_index = index
        assert tabs.get_tab_frame_boxes_for_session_id("video", VideoDataLayerGroup.TRACKING).frame_data_boxes == []
        assert store.has_frame_for_layer_at_frame_index(VideoDataLayer.D, index)


def test_directional_deletion_rejects_invalid_direction_without_modifying_data():
    service = TrackingLayerService.__new__(TrackingLayerService)
    QObject.__init__(service)
    service._app_adapter = MagicMock()
    with pytest.raises(UnsupportedDirectionException):
        service.delete_tracks_by_id_and_direction("video", "-4", "invalid")
    service._app_adapter.get_session_by_id.return_value.data.delete_boxes_from_layer_by_id_at_frame_index.assert_not_called()
