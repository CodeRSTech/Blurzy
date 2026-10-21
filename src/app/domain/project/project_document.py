from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ProjectDirectories:
    """Remember project-scoped import/export locations and filename affixes.

    Layer: Domain.
    Context: A value object persisted with a project, separate from application
    preferences so reopening the project restores its own file locations.

    Attributes:
        last_import_directory: Most recently used source directory.
        last_export_directory: Most recently used destination directory.
        export_prefix: Prefix applied to exported filenames.
        export_suffix: Suffix applied to exported filenames.
    """

    last_import_directory: str = ""
    last_export_directory: str = ""
    export_prefix: str = ""
    export_suffix: str = ""


@dataclass(slots=True)
class ProjectSessionDocument:
    """Persist the reopenable state for one video session.

    Layer: Domain.
    Context: Project serialization stores paths and plain-data settings/layers;
    runtime video handles and worker state are reconstructed when loading.

    Attributes:
        video_path: Path identifying the source video.
        current_frame_index: Frame to select when the session is restored.
        next_annotation_id: Next identifier available for manual annotations.
        settings: Serializable processing settings for the session.
        layers: Layer names mapped to frame-indexed box payloads.
    """

    video_path: str
    current_frame_index: int
    next_annotation_id: int
    settings: dict[str, object]
    layers: dict[str, dict[str, list[dict[str, object]]]]


@dataclass(slots=True)
class ProjectDocument:
    """Top-level, versioned document for saving and restoring a project.

    Layer: Domain.
    Context: This data-only object is the boundary between project
    orchestration and the JSON-backed infrastructure store.

    Attributes:
        format_version: Serialized schema version supported by the store.
        active_session_path: Video path of the active session, if any.
        directories: Project-local import/export locations and filename affixes.
        sessions: Session documents included in the project.
    """

    format_version: str = "1.0"
    active_session_path: str = ""
    directories: ProjectDirectories = field(default_factory=ProjectDirectories)
    sessions: list[ProjectSessionDocument] = field(default_factory=list)
