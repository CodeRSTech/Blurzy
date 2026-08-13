"""Thin UI-layer facade over the concrete ``UIController`` object."""

from __future__ import annotations

from typing import TYPE_CHECKING


from app.ui.interfaces.controller_interface import UIControllerInterface
if TYPE_CHECKING:
    from app.domain import SessionId


if TYPE_CHECKING:
	from app.ui.uicontroller import UIController


class UIControllerAdapter(UIControllerInterface):
	"""Expose only controller operations currently needed by migrated handlers."""

	def __init__(self, controller: UIController) -> None:
		self._controller = controller

	def __repr__(self) -> str:
		return f"<UIControllerAdapter wrapping={self._controller!r}>"

	def render_frame_for_session_id(self, s_id: SessionId) -> None:
		self._controller.render_frame_for_session_id(s_id)

	def update_ui_status_bar(self) -> None:
		self._controller.update_ui_status_bar()

