"""Module for session file list view model; defines application concepts without UI or infrastructure dependencies.

See Also:
    - [`SessionId`][app.domain.session.session_id.SessionId] — identifies each listed session
    - [`SessionHandler`][app.ui.handlers.session_handler.SessionHandler] — manages sessions shown in the UI

Layer: Domain.
Context: Defines application concepts without ui or infrastructure dependencies at this architectural boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


from dataclasses import dataclass
if TYPE_CHECKING:
    from app.domain.session import SessionId





@dataclass(slots=True)
class SessionFileListViewModel:
    """
    Display model for session list item (left panel).

    Attributes:
        s_id (SessionId): Session identifier for the file.
        title (str): Filename, such as `"video.mp4"`.
        subtitle (str): Metadata summary, such as resolution, FPS, and frame count.

    Note:
        Populated by the `list_of_session_list_view_models()` factory.


Layer: Domain.
Context: Represents application concepts without UI or infrastructure dependencies.
"""

    s_id: SessionId
    title: str
    subtitle: str
