from __future__ import annotations

from dataclasses import dataclass

from app.domain.session import SessionId


@dataclass(slots=True)
class SessionFileListViewModel:
    """
    Display model for session list item (left panel).

    Attributes:
        s_id (SessionId): Session identifier for the file.
        title (str): Filename, such as ``"video.mp4"``.
        subtitle (str): Metadata summary, such as resolution, FPS, and frame count.

    Note:
        Populated by the ``list_of_session_list_view_models()`` factory.
    """

    s_id: SessionId
    title: str
    subtitle: str
