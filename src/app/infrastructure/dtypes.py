"""Module for dtypes; implements concrete processing and I/O behind application-facing contracts.

Layer: Infrastructure.
Context: Implements concrete processing and i/o behind application-facing contracts at this architectural boundary.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from numpy import ndarray, dtype, uint8

__all__ = ["RGBFrame"]


# RGB frame — numpy array (height, width, 3 channels) with uint8 values
type RGBFrame = ndarray[tuple[int, int, int], dtype[uint8]]