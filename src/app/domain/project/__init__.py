"""Project domain models for save/load persistence.

See Also:
    - [`ProjectService`][app.application.services.project_service.ProjectService] — coordinates project workflows
    - [`ProjectStore`][app.infrastructure.project.project_store.ProjectStore] — persists project documents

Layer: Domain.
Context: Defines application concepts independently of UI and infrastructure implementations.
"""

from .project_document import ProjectDirectories, ProjectDocument, ProjectSessionDocument

__all__ = [
    "ProjectDirectories",
    "ProjectDocument",
    "ProjectSessionDocument",
]
