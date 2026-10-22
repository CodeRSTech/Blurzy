"""Direction enumeration for frame navigation and copying.

See Also:
    - [`PlaybackState`][app.domain.video.playback_state.PlaybackState] — stores the current playback position
    - [`TrackingLayerService`][app.application.services.tracking.layer_service.TrackingLayerService] — uses direction when propagating annotations

Layer: Domain.
Context: Defines application concepts independently of UI and infrastructure implementations.
"""

from enum import Enum


class Direction(Enum):
    """
    Direction of movement for frame navigation and detection copying.

    Note:
        `PREV` moves backward in time with value `-1` and `NEXT` moves
        forward with value `1`. The enum values intentionally match frame
        index deltas so callers can use them directly for navigation, copying
        boxes to adjacent frames, or deleting data in a direction.

    Example:
        current_idx = 100
        direction = Direction.NEXT
        target_idx = current_idx + direction.value  # 101


Layer: Domain.
Context: Represents application concepts without UI or infrastructure dependencies.
"""
    PREV = -1
    NEXT = 1