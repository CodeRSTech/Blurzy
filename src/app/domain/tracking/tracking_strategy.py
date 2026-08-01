"""Tracking algorithm strategy enumeration (currently only Hungarian implemented)."""

from __future__ import annotations

from enum import Enum


class TrackingStrategy(str, Enum):
    """
    Multi-object tracking algorithm selection.

    Note:
        ``DUMMY`` is a pass-through strategy and ``HUNGARIAN`` is the primary
        implemented tracker using IoU matching. ``BYTRACK``, ``DEEP_SORT``, and
        ``CSRT`` are placeholders for future implementations. Selected from the
        settings dropdown and used by ``TrackingService`` to instantiate the
        appropriate worker. The current default is ``HUNGARIAN``.
    """
    DUMMY = "dummy"
    HUNGARIAN = "hungarian"
    BYTRACK = "bytetrack"
    DEEP_SORT = "deepsort"
    CSRT = "csrt"
