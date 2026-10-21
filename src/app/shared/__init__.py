"""Package for shared; provides reusable helpers across application layers.

Layer: Shared utilities.
Context: Provides reusable helpers across application layers at this architectural boundary.
"""

from app.shared.logging_cfg import configure_logging, get_logger

__all__ = [
    "configure_logging",
    "get_logger",
]
