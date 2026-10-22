"""Serializes project documents to JSON and validates them when reading.

See Also:
    - [`ProjectDocument`][app.domain.project.project_document.ProjectDocument] — document model persisted by this store
    - [`ProjectService`][app.application.services.project_service.ProjectService] — coordinates project persistence

Layer: Infrastructure.
Context: Implements concrete processing and i/o behind application-facing contracts at this architectural boundary.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict

from app.domain.project import ProjectDirectories, ProjectDocument, ProjectSessionDocument
from app.shared.exceptions import ProjectFormatException


class ProjectStore:
    """Read and write versioned project documents as JSON.

    Layer: Infrastructure.
    Context: Encodes domain project data at the filesystem boundary and
    validates the persisted structure before constructing domain objects.
    """

    _SUPPORTED_VERSION = "1.0"

    def save(self, file_path: str, project: ProjectDocument) -> None:
        """Serialize a project document to the specified path.

        Args:
            file_path: Destination JSON file; its parent directory is created
                when necessary.
            project: Domain document to serialize.

        Raises:
            OSError: If the destination directory cannot be created or the file
                cannot be written.
            TypeError: If the destination path or a project value has an
                unsupported type.
            ValueError: If serialization encounters a circular reference.
        """
        parent = os.path.dirname(file_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as fh:
            json.dump(asdict(project), fh, indent=2)

    def load(self, file_path: str) -> ProjectDocument:
        """Read JSON from disk and validate it as a supported project.

        Args:
            file_path: Source project JSON file.

        Returns:
            The decoded domain project document.

        Raises:
            OSError: If the file cannot be opened or read.
            UnicodeDecodeError: If the file is not valid UTF-8.
            json.JSONDecodeError: If the file does not contain valid JSON.
            ProjectFormatException: If the payload has an unsupported version
                or an invalid required structure.
            TypeError: If a numeric field has an incompatible type.
            ValueError: If a numeric field cannot be converted to an integer.
        """
        with open(file_path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        return self._to_document(payload)

    def _to_document(self, payload: object) -> ProjectDocument:
        if not isinstance(payload, dict):
            raise ProjectFormatException("expected a JSON object at the root.")

        version = payload.get("format_version")
        if version != self._SUPPORTED_VERSION:
            raise ProjectFormatException(
                f"unsupported format version '{version}'. Expected '{self._SUPPORTED_VERSION}'."
            )

        directories_raw = payload.get("directories", {})
        if not isinstance(directories_raw, dict):
            raise ProjectFormatException("'directories' must be an object.")

        sessions_raw = payload.get("sessions", [])
        if not isinstance(sessions_raw, list):
            raise ProjectFormatException("'sessions' must be a list.")

        sessions: list[ProjectSessionDocument] = []
        for entry in sessions_raw:
            if not isinstance(entry, dict):
                raise ProjectFormatException("each session entry must be an object.")
            video_path = entry.get("video_path", "")
            settings = entry.get("settings", {})
            layers = entry.get("layers", {})
            if not isinstance(video_path, str) or not video_path.strip():
                raise ProjectFormatException("session 'video_path' must be a non-empty string.")
            if not isinstance(settings, dict):
                raise ProjectFormatException(f"session '{video_path}' has invalid 'settings'.")
            if not isinstance(layers, dict):
                raise ProjectFormatException(f"session '{video_path}' has invalid 'layers'.")
            sessions.append(
                ProjectSessionDocument(
                    video_path=video_path,
                    current_frame_index=int(entry.get("current_frame_index", 0)),
                    next_annotation_id=int(entry.get("next_annotation_id", 1)),
                    settings=settings,
                    layers=layers,
                )
            )

        return ProjectDocument(
            format_version=self._SUPPORTED_VERSION,
            active_session_path=str(payload.get("active_session_path", "")),
            directories=ProjectDirectories(
                last_import_directory=str(directories_raw.get("last_import_directory", "")),
                last_export_directory=str(directories_raw.get("last_export_directory", "")),
                export_prefix=str(directories_raw.get("export_prefix", "")),
                export_suffix=str(directories_raw.get("export_suffix", "")),
            ),
            sessions=sessions,
        )
