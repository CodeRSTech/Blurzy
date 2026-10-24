"""
Shared UI-controller contract consumed by UI handlers.

This protocol is intentionally small and UI-owned. It models only the
controller operations handlers actually need, while keeping handlers from
depending on the entire concrete `UIController` surface.

See Also:
    - [`UIController`][app.ui.uicontroller.UIController] — provides the controller operations
    - [`UIControllerAdapter`][app.ui.adapters.controller_adapter.UIControllerAdapter] — adapts it for handler access


Layer: Presentation.
Context: Defines presentation-facing contracts for controllers, application access, and windows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


from typing import Protocol
if TYPE_CHECKING:
    from app.domain import SessionId




class UIControllerInterface(Protocol):
	"""
	Narrow controller facade exposed to handlers.

	Layer: Presentation.
	Context: Supports user interaction and delegates application work through presentation contracts.
	"""

	def render_frame_for_session_id(self, s_id: SessionId) -> None:
		"""
		Render frame for session id.

		Args:
		    s_id: Identifier of the target session. (SessionId).
		"""
		...

	def update_ui_status_bar(self) -> None:
		"""
		Update ui status bar.
		"""
		...

