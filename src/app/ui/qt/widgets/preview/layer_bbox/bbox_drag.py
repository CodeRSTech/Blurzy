from __future__ import annotations

from enum import Enum, auto

from PySide6.QtCore import Qt


class DragMode(Enum):
    NONE = auto()
    DRAW = auto()
    MOVE = auto()
    TOP_LEFT = auto()
    TOP_RIGHT = auto()
    BOT_LEFT = auto()
    BOT_RIGHT = auto()
    TOP = auto()
    BOTTOM = auto()
    LEFT = auto()
    RIGHT = auto()


CORNER_CURSOR = {
    DragMode.TOP_LEFT: Qt.CursorShape.SizeFDiagCursor,
    DragMode.TOP_RIGHT: Qt.CursorShape.SizeBDiagCursor,
    DragMode.BOT_LEFT: Qt.CursorShape.SizeBDiagCursor,
    DragMode.BOT_RIGHT: Qt.CursorShape.SizeFDiagCursor,
    DragMode.TOP: Qt.CursorShape.SizeVerCursor,
    DragMode.BOTTOM: Qt.CursorShape.SizeVerCursor,
    DragMode.LEFT: Qt.CursorShape.SizeHorCursor,
    DragMode.RIGHT: Qt.CursorShape.SizeHorCursor,
    DragMode.MOVE: Qt.CursorShape.SizeAllCursor,
}


