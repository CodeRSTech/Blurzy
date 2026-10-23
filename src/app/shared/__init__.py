"""
Package for shared; provides reusable helpers across application layers.

See Also:
    - [`configure_logging`][app.shared.logging_cfg.configure_logging] — configures application logging
    - [`runtime_config`][app.shared.runtime_config] — parses startup configuration values

Layer: Shared utilities.
Context: Provides reusable helpers across application layers at this architectural boundary.
"""

from app.shared.logging_cfg import configure_logging, get_logger

__all__ = [
    "configure_logging",
    "get_logger",
]
