"""Factory for converting Session objects to UI view model (list display)."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.infrastructure.session.session import Session
from app.domain.views import SessionFileListViewModel


def list_of_session_list_view_models(sessions: list[Session]) -> list[SessionFileListViewModel]:
    """
    Convert Session objects to ``SessionFileListViewModel`` for UI list display.

    Note:
        Maps ``session.view_state.metadata`` to the subtitle format
        ``"WxH | FPS fps | N frames"``.
    """
    session_files: list[SessionFileListViewModel] = []
    for session in sessions:
        m = session.state.metadata
        session_files.append(
            SessionFileListViewModel(
                s_id=session.s_id,
                title=session.s_id.basename,
                subtitle=f"{m.width}x{m.height} | {m.fps:.2f} fps | {m.frame_count} frames",
            )
        )

    return session_files
