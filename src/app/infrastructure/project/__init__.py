"""Project persistence infrastructure.

See Also:
    - [`ProjectStore`][app.infrastructure.project.project_store.ProjectStore] — persists project documents
    - [`ProjectService`][app.application.services.project_service.ProjectService] — coordinates save and load workflows

Layer: Infrastructure.
Context: Implements concrete processing and I/O behind application-facing contracts.
"""

from .project_store import ProjectStore

__all__ = ["ProjectStore"]
