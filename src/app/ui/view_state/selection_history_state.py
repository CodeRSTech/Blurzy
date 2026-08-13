from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass(slots=True)
class SelectionHistoryEntry:
    before_keys: list[str]
    after_keys: list[str]


@dataclass(slots=True)
class BoxMutationEntry:
    frame_index: int
    before_boxes: list
    after_boxes: list
    before_selection: list[str]
    after_selection: list[str]


@dataclass(slots=True)
class CopiedBBoxSnapshot:
    label: str
    bbox_xyxy: tuple[int, int, int, int]
    color_hex: str


class SelectionHistoryState:
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
        key = (session_id, tab_index)
        if before_keys == after_keys:
            return
        self._selection_undo[key].append(
            SelectionHistoryEntry(before_keys=list(before_keys), after_keys=list(after_keys))
        )
        self._selection_redo[key].clear()

    def undo_selection(self, *, session_id: str, tab_index: int) -> list[str] | None:
        key = (session_id, tab_index)
        if not self._selection_undo[key]:
            return None
        entry = self._selection_undo[key].pop()
        self._selection_redo[key].append(entry)
        return list(entry.before_keys)

    def redo_selection(self, *, session_id: str, tab_index: int) -> list[str] | None:
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
        key = (session_id, tab_index)
        if not self._mutation_undo[key]:
            return None
        entry = self._mutation_undo[key].pop()
        self._mutation_redo[key].append(entry)
        return entry

    def redo_box_mutation(self, *, session_id: str, tab_index: int) -> BoxMutationEntry | None:
        key = (session_id, tab_index)
        if not self._mutation_redo[key]:
            return None
        entry = self._mutation_redo[key].pop()
        self._mutation_undo[key].append(entry)
        return entry

    def set_clipboard_boxes(self, *, boxes: list[CopiedBBoxSnapshot], tab_index: int) -> None:
        self._clipboard_boxes = list(boxes)
        self._clipboard_tab_index = tab_index

    @property
    def has_clipboard_boxes(self) -> bool:
        return bool(self._clipboard_boxes)

    def get_clipboard_boxes(self) -> list[CopiedBBoxSnapshot]:
        return list(self._clipboard_boxes)
