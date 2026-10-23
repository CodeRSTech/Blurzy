"""
Module for selection history state; stores transient interaction state.

See Also:
    - [`BBoxViewModel`][app.domain.views.bounding_box_view_model.BBoxViewModel] — snapshots box data for undo and redo
    - [`AnnotationHandler`][app.ui.handlers.annotation_handler.AnnotationHandler] — applies recorded selection mutations

Layer: Presentation.
Context: Stores transient interaction state at this architectural boundary.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass(slots=True)
class SelectionHistoryEntry:
    """
    Store the selected box keys before and after one selection change.

    Attributes:
        before_keys: Selection to restore when undoing the change.
        after_keys: Selection to restore when redoing the change.

    Layer: Presentation.
    Context: Supports user interaction and delegates application work through presentation contracts.
    """
    before_keys: list[str]
    after_keys: list[str]


@dataclass(slots=True)
class BoxMutationEntry:
    """
    Store one frame's box and selection snapshots for undo or redo.

    Attributes:
        frame_index: Frame whose boxes were mutated.
        before_boxes: Boxes captured before the mutation.
        after_boxes: Boxes captured after the mutation.
        before_selection: Selected keys captured before the mutation.
        after_selection: Selected keys captured after the mutation.

    Layer: Presentation.
    Context: Supports user interaction and delegates application work through presentation contracts.
    """
    frame_index: int
    before_boxes: list
    after_boxes: list
    before_selection: list[str]
    after_selection: list[str]


@dataclass(slots=True)
class CopiedBBoxSnapshot:
    """
    Store the box fields needed to paste a copied annotation.

    Attributes:
        label: Classification label to copy.
        bbox_xyxy: Image-space `(x1, y1, x2, y2)` coordinates.
        color_hex: Display color to apply to the pasted box.

    Layer: Presentation.
    Context: Supports user interaction and delegates application work through presentation contracts.
    """
    label: str
    bbox_xyxy: tuple[int, int, int, int]
    color_hex: str


class SelectionHistoryState:
    """
    Represent selection history state.

    Layer: Presentation.
    Context: Supports user interaction and delegates application work through presentation contracts.
    """
    def __init__(self) -> None:
        self._selection_undo: dict[tuple[str, int], list[SelectionHistoryEntry]] = defaultdict(list)
        self._selection_redo: dict[tuple[str, int], list[SelectionHistoryEntry]] = defaultdict(list)
        self._mutation_undo: dict[tuple[str, int], list[BoxMutationEntry]] = defaultdict(list)
        self._mutation_redo: dict[tuple[str, int], list[BoxMutationEntry]] = defaultdict(list)
        self._clipboard_boxes: list[CopiedBBoxSnapshot] = []
        self._clipboard_tab_index: int | None = None

    def record_selection_change(
        self,
        *,
        session_id: str,
        tab_index: int,
        before_keys: list[str],
        after_keys: list[str],
    ) -> None:
        """
        Push a selection change onto the undo stack for one session and tab.

        Args:
            session_id: Session whose selection changed.
            tab_index: Data tab whose selection changed.
            before_keys: Selected box keys before the change.
            after_keys: Selected box keys after the change.

        Side Effects:
            Does nothing for equal selections; otherwise records the change and clears redo history.
        """
        key = (session_id, tab_index)
        if before_keys == after_keys:
            return
        self._selection_undo[key].append(
            SelectionHistoryEntry(before_keys=list(before_keys), after_keys=list(after_keys))
        )
        self._selection_redo[key].clear()

    def undo_selection(self, *, session_id: str, tab_index: int) -> list[str] | None:
        """
        Move the latest selection change to redo history and return its prior selection.

        Args:
            session_id: Session whose selection history is traversed.
            tab_index: Data tab whose selection history is traversed.

        Returns:
            Copy of the prior selected keys, or `None` when no undo entry exists.
        """
        key = (session_id, tab_index)
        if not self._selection_undo[key]:
            return None
        entry = self._selection_undo[key].pop()
        self._selection_redo[key].append(entry)
        return list(entry.before_keys)

    def redo_selection(self, *, session_id: str, tab_index: int) -> list[str] | None:
        """
        Move the latest undone selection change back to undo history.

        Args:
            session_id: Session whose selection history is traversed.
            tab_index: Data tab whose selection history is traversed.

        Returns:
            Copy of the restored selected keys, or `None` when no redo entry exists.
        """
        key = (session_id, tab_index)
        if not self._selection_redo[key]:
            return None
        entry = self._selection_redo[key].pop()
        self._selection_undo[key].append(entry)
        return list(entry.after_keys)

    def record_box_mutation(
        self,
        *,
        session_id: str,
        tab_index: int,
        frame_index: int,
        before_boxes: list,
        after_boxes: list,
        before_selection: list[str],
        after_selection: list[str],
    ) -> None:
        """
        Record before/after box and selection snapshots for undo.

        Args:
            session_id: Session whose boxes changed.
            tab_index: Data tab where the mutation occurred.
            frame_index: Zero-based index of the edited frame.
            before_boxes: Box list captured before the edit.
            after_boxes: Box list captured after the edit.
            before_selection: Selected keys before the edit.
            after_selection: Selected keys after the edit.

        Side Effects:
            Appends an undo entry and clears redo history for this session and tab.
        """
        key = (session_id, tab_index)
        self._mutation_undo[key].append(
            BoxMutationEntry(
                frame_index=frame_index,
                before_boxes=list(before_boxes),
                after_boxes=list(after_boxes),
                before_selection=list(before_selection),
                after_selection=list(after_selection),
            )
        )
        self._mutation_redo[key].clear()

    def undo_box_mutation(self, *, session_id: str, tab_index: int) -> BoxMutationEntry | None:
        """
        Move the latest box mutation to redo history and return its snapshots.

        Args:
            session_id: Session whose mutation history is traversed.
            tab_index: Data tab whose mutation history is traversed.

        Returns:
            Mutation snapshot to restore, or `None` when no undo entry exists.
        """
        key = (session_id, tab_index)
        if not self._mutation_undo[key]:
            return None
        entry = self._mutation_undo[key].pop()
        self._mutation_redo[key].append(entry)
        return entry

    def redo_box_mutation(self, *, session_id: str, tab_index: int) -> BoxMutationEntry | None:
        """
        Move the latest undone box mutation back to undo history.

        Args:
            session_id: Session whose mutation history is traversed.
            tab_index: Data tab whose mutation history is traversed.

        Returns:
            Mutation snapshot to reapply, or `None` when no redo entry exists.
        """
        key = (session_id, tab_index)
        if not self._mutation_redo[key]:
            return None
        entry = self._mutation_redo[key].pop()
        self._mutation_undo[key].append(entry)
        return entry

    def set_clipboard_boxes(self, *, boxes: list[CopiedBBoxSnapshot], tab_index: int) -> None:
        """
        Replace the copied-box clipboard with snapshots from one data tab.

        Args:
            boxes: Box snapshots available for pasting.
            tab_index: Tab index from which the boxes were copied.
        """
        self._clipboard_boxes = list(boxes)
        self._clipboard_tab_index = tab_index

    @property
    def has_clipboard_boxes(self) -> bool:
        """
        Return whether the clipboard contains any copied boxes.

        Returns:
            `True` when at least one copied box is stored.
        """
        return bool(self._clipboard_boxes)

    def get_clipboard_boxes(self) -> list[CopiedBBoxSnapshot]:
        """
        Return a shallow copy of the copied-box clipboard.

        Returns:
            List of clipboard snapshots; the list is copied, but its entries are shared.
        """
        return list(self._clipboard_boxes)
