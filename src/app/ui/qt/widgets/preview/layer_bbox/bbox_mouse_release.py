"""Module for bbox mouse release; implements the Qt presentation components.

Layer: Presentation.
Context: Implements the qt presentation components at this architectural boundary.
"""

from enum import Enum, auto


class MouseReleaseOutcome(Enum):
    """Represent mouse release outcome.

Layer: Presentation.
Context: Supports user interaction and delegates application work through presentation contracts.
"""
    NONE = auto()
    DRAW = auto()
    EDIT = auto()
    CANCEL = auto()