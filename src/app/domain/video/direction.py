"""Direction enumeration for frame navigation and copying."""

from enum import Enum


class Direction(Enum):
    """
    Direction of movement for frame navigation and detection copying.

    Note:
        ``PREV`` moves backward in time with value ``-1`` and ``NEXT`` moves
        forward with value ``1``. The enum values intentionally match frame
        index deltas so callers can use them directly for navigation, copying
        boxes to adjacent frames, or deleting data in a direction.

    Example:
        current_idx = 100
        direction = Direction.NEXT
        target_idx = current_idx + direction.value  # 101
    """
    PREV = -1
    NEXT = 1