"""Tracking algorithm strategy enumeration."""

from __future__ import annotations

from enum import Enum


class TrackingStrategy(str, Enum):
    """
    Multi-object tracking algorithm selection.

    Note:
        ``DUMMY`` is a pass-through strategy and ``HUNGARIAN`` is the primary
        motion-only tracker using IoU matching. ``DEEP_SORT`` uses an age
        cascade with an appearance gallery, while ``BOT_SORT`` combines
        ByteTrack's two-stage association with EMA Re-ID appearance features and
        direct width/height Kalman state estimation. ``BYTRACK`` and ``CSRT``
        remain additional strategy selections. The current default is
        ``HUNGARIAN``.
    """
    DUMMY = "dummy"
    HUNGARIAN = "hungarian"
    BOT_SORT = "botsort"
    BYTRACK = "bytetrack"
    DEEP_SORT = "deepsort"
    CSRT = "csrt"
