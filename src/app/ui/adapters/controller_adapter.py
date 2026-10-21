"""Thin UI-layer facade over the concrete `UIController` object.

Layer: Presentation.
Context: Bridges UI-facing contracts to application operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


from app.ui.interfaces.controller_interface import UIControllerInterface
if TYPE_CHECKING:
    from app.domain import SessionId


if TYPE_CHECKING:
	from app.ui.uicontroller import UIController


class UIControllerAdapter(UIControllerInterface):
	"""Expose only controller operations currently needed by migrated handlers.

Layer: Presentation.
Context: Supports user interaction and delegates application work through presentation contracts.


    Args:
        controller: Controller whose window, application facade, and rendering callbacks are exposed to handlers.
"""

	def __init__(self, controller: UIController) -> None:
		self._controller = controller

	def __repr__(self) -> str:
		return f"<UIControllerAdapter wrapping={self._controller!r}>"

	def render_frame_for_session_id(self, s_id: SessionId) -> None:
		"""Render frame for session id.

		Args:
		    s_id: Identifier of the target session. (SessionId)."""
		self._controller.render_frame_for_session_id(s_id)

	def update_ui_status_bar(self) -> None:
		"""Update ui status bar."""
		self._controller.update_ui_status_bar()
