from __future__ import annotations

from types import SimpleNamespace

from app.ui.handlers.playback_handler import PlaybackHandler


def test_rotate_requested_updates_manual_rotation_and_rerenders() -> None:
    render_calls: list[str] = []
    reset_calls: list[bool] = []
    rotation_updates: list[int] = []
    session = SimpleNamespace(video_reader=SimpleNamespace(manual_rotation=0))
    handler = PlaybackHandler.__new__(PlaybackHandler)
    handler._app = SimpleNamespace(get_session_by_id=lambda s_id: session)
    handler._window = SimpleNamespace(
        selected_s_id="session-1",
        preview_container=SimpleNamespace(reset_viewport=lambda: reset_calls.append(True)),
        transport_panel=SimpleNamespace(set_rotation_degrees=lambda value: rotation_updates.append(value)),
        show_error=lambda title, msg: (_ for _ in ()).throw(AssertionError(f"Unexpected error: {title}: {msg}")),
    )
    handler._controller = SimpleNamespace(render_frame_for_session_id=lambda s_id: render_calls.append(s_id))

    handler.on_rotate_requested(90)

    assert session.video_reader.manual_rotation == 90
    assert reset_calls == [True]
    assert rotation_updates == [90]
    assert render_calls == ["session-1"]


def test_fit_view_requested_resets_preview_viewport() -> None:
    reset_calls: list[bool] = []
    handler = PlaybackHandler.__new__(PlaybackHandler)
    handler._window = SimpleNamespace(
        preview_container=SimpleNamespace(reset_viewport=lambda: reset_calls.append(True))
    )

    handler.on_fit_view_requested()

    assert reset_calls == [True]
