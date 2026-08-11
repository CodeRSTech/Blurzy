from app.ui.view_state.bbox_selection_state import BBoxSelectionState


def test_selection_tracks_keys_and_can_clear() -> None:
    state = BBoxSelectionState()

    state.select("box-a")
    state.toggle("box-b")
    state.toggle("box-a")

    assert state.is_selected("box-b") is True
    assert state.is_selected("box-a") is False
    assert state.count() == 1

    state.clear()

    assert state.get_selected_keys() == []


def test_invert_and_select_all() -> None:
    state = BBoxSelectionState()
    state.set_selection(["box-a", "box-b"])
    state.invert(["box-a", "box-b", "box-c"])

    assert state.get_selected_keys() == ["box-c"]

    state.select_all(["box-a", "box-b"])
    assert set(state.get_selected_keys()) == {"box-a", "box-b", "box-c"}
