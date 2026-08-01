"""Shared UI-controller contract consumed by UI handlers.

This protocol is intentionally small and UI-owned. It models only the
controller operations handlers actually need, while keeping handlers from
depending on the entire concrete ``UIController`` surface.
"""

from __future__ import annotations

from typing import Protocol

from app.domain import SessionId


class UIControllerInterface(Protocol):
	"""Narrow controller facade exposed to handlers."""

	def render_frame_for_session_id(self, s_id: SessionId) -> None:
		...

	def update_ui_status_bar(self) -> None:
		...

