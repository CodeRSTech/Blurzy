from enum import Enum, auto


class MouseReleaseOutcome(Enum):
    NONE = auto()
    DRAW = auto()
    EDIT = auto()
    CANCEL = auto()