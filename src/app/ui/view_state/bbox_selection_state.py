"""Box selection state container.

Maintains the set of selected box keys for a given session and tab.
This is the single source of truth for which boxes are currently selected.
"""

from __future__ import annotations

from typing import final


@final
class BBoxSelectionState:
    """Shared box-key selection container for a given session and tab.
    
    Scoped by (session_id, tab_index) pair. Provides methods to query,
    update, and inspect the current selection.
    """

    def __init__(self) -> None:
        """Initialize empty selection."""
        self._selected: set[str] = set()

    def select(self, key: str) -> None:
        """Add a single box key to the selection."""
        self._selected.add(key)

    def deselect(self, key: str) -> None:
        """Remove a single box key from the selection."""
        self._selected.discard(key)

    def toggle(self, key: str) -> None:
        """Toggle the selection state of a single box key."""
        if key in self._selected:
            self._selected.discard(key)
        else:
            self._selected.add(key)

    def set_selection(self, keys: list[str]) -> None:
        """Replace the entire selection with the given keys."""
        self._selected = set(keys)

    def clear(self) -> None:
        """Clear the selection."""
        self._selected.clear()

    def get_selected_keys(self) -> list[str]:
        """Return the list of currently selected box keys."""
        return list(self._selected)

    def is_selected(self, key: str) -> bool:
        """Check if a box key is selected."""
        return key in self._selected

    def select_all(self, keys: list[str]) -> None:
        """Select all keys in the provided list."""
        self._selected.update(keys)

    def invert(self, all_keys: list[str]) -> None:
        """Invert selection: select what's not selected, deselect what is."""
        all_set = set(all_keys)
        self._selected = all_set - self._selected

    def has_selection(self) -> bool:
        """Check if any boxes are selected."""
        return len(self._selected) > 0

    def count(self) -> int:
        """Return the number of selected boxes."""
        return len(self._selected)
