"""Box selection state container.

Maintains the set of selected box keys for a given session and tab.
This is the single source of truth for which boxes are currently selected.

See Also:
    - [`BBoxViewModel`][app.domain.views.bounding_box_view_model.BBoxViewModel] — identifies selectable boxes
    - [`AnnotationOverlayWidget`][app.ui.qt.widgets.preview.layer_bbox.layer_bbox.AnnotationOverlayWidget] — reflects selection in the preview


Layer: Presentation.
Context: Stores transient state used by presentation interactions.
"""

from __future__ import annotations

from typing import final


@final
class BBoxSelectionState:
    """Shared box-key selection container for a given session and tab.

    Scoped by (session_id, tab_index) pair. Provides methods to query,
    update, and inspect the current selection.


Layer: Presentation.
Context: Supports user interaction and delegates application work through presentation contracts.
"""

    def __init__(self) -> None:
        """Initialize empty selection."""
        self._selected: set[str] = set()

    def select(self, key: str) -> None:
        """Add a single box key to the selection.

        Args:
            key: Key of the box to select.
        """
        self._selected.add(key)

    def deselect(self, key: str) -> None:
        """Remove a single box key from the selection.

        Args:
            key: Key of the box to remove from the selection.
        """
        self._selected.discard(key)

    def toggle(self, key: str) -> None:
        """Toggle the selection state of a single box key.

        Args:
            key: Key whose selected state should be toggled.
        """
        if key in self._selected:
            self._selected.discard(key)
        else:
            self._selected.add(key)

    def set_selection(self, keys: list[str]) -> None:
        """Replace the entire selection with the given keys.

        Args:
            keys: Box keys that should become the complete selection.
        """
        self._selected = set(keys)

    def clear(self) -> None:
        """Clear the selection."""
        self._selected.clear()

    def get_selected_keys(self) -> list[str]:
        """Return the list of currently selected box keys.

        Returns:
            List of selected box keys; ordering is unspecified.
        """
        return list(self._selected)

    def is_selected(self, key: str) -> bool:
        """Check if a box key is selected.

        Args:
            key: Box key to check.

        Returns:
            `True` if `key` is currently selected.
        """
        return key in self._selected

    def select_all(self, keys: list[str]) -> None:
        """Select all keys in the provided list.

        Args:
            keys: Box keys to add to the current selection.
        """
        self._selected.update(keys)

    def invert(self, all_keys: list[str]) -> None:
        """Invert selection: select what's not selected, deselect what is.

        Args:
            all_keys: Complete set of keys eligible for selection.
        """
        all_set = set(all_keys)
        self._selected = all_set - self._selected

    def has_selection(self) -> bool:
        """Check if any boxes are selected.

        Returns:
            `True` when the selection contains at least one key.
        """
        return len(self._selected) > 0

    def count(self) -> int:
        """Return the number of selected boxes.

        Returns:
            Number of currently selected box keys.
        """
        return len(self._selected)
