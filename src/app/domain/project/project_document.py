from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ProjectDirectories:
    last_import_directory: str = ""
    last_export_directory: str = ""
    export_prefix: str = ""
    export_suffix: str = ""


@dataclass(slots=True)
class ProjectSessionDocument:
    video_path: str
    current_frame_index: int
    next_annotation_id: int
    settings: dict[str, object]
    layers: dict[str, dict[str, list[dict[str, object]]]]


@dataclass(slots=True)
class ProjectDocument:
    format_version: str = "1.0"
    active_session_path: str = ""
    directories: ProjectDirectories = field(default_factory=ProjectDirectories)
    sessions: list[ProjectSessionDocument] = field(default_factory=list)
