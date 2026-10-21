"""Project persistence infrastructure.

Layer: Infrastructure.
Context: Implements concrete processing and I/O behind application-facing contracts.
"""

from .project_store import ProjectStore

__all__ = ["ProjectStore"]
