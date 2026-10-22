"""Captures and restores project state through the application and project store.

See Also:
    - [`ProjectStore`][app.infrastructure.project.project_store.ProjectStore] — persists project documents
    - [`ProjectDocument`][app.domain.project.project_document.ProjectDocument] — represents the saved project structure

Layer: Application.
Context: Implements use cases by coordinating domain and infrastructure operations at this architectural boundary.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from app.domain.export import ProcessingSettings
from app.domain.project import ProjectDirectories, ProjectDocument, ProjectSessionDocument
from app.domain.session import SessionId
from app.infrastructure.project import ProjectStore
from app.shared.logging_cfg import get_logger

if TYPE_CHECKING:
    from app.application.application import Application


logger = get_logger("Application->ProjectService")


@dataclass(slots=True)
class ProjectLoadReport:
    """Summarize which project sessions were restored successfully.

    Layer: Application.
    Context: Returned to callers after project restoration; missing or
    unopenable source videos are reported rather than aborting other sessions.

    Attributes:
        restored_sessions: Number of sessions opened and restored.
        skipped_session_paths: Video paths that could not be restored.
    """

    restored_sessions: int
    skipped_session_paths: list[str]


class ProjectService:
    """Coordinate project persistence with application session management.

    Layer: Application.
    Context: Captures serializable session state through the application,
    delegates file encoding to `ProjectStore`, and restores sessions while
    reporting per-video failures.

    Args:
        app: Application facade whose session manager and video operations are
            used to capture and restore project sessions.
    """

    def __init__(self, app: Application) -> None:
        self._app = app
        self._store = ProjectStore()
        self._current_project_path = ""
        self._directories = ProjectDirectories()

    @property
    def current_project_path(self) -> str:
        """Return the path of the currently loaded or most recently saved project.

        Returns:
            The project file path, or an empty string when no project is active.
        """
        return self._current_project_path

    @property
    def directories(self) -> ProjectDirectories:
        """Return the mutable project-specific import/export directory settings.

        Returns:
            The current `ProjectDirectories` value object.
        """
        return self._directories

    def update_directories(
        self,
        *,
        last_import_directory: str | None = None,
        last_export_directory: str | None = None,
        export_prefix: str | None = None,
        export_suffix: str | None = None,
    ) -> None:
        """Update only the supplied project directory or export-name settings.

        Args:
            last_import_directory: Optional most recently used import directory.
            last_export_directory: Optional most recently used export directory.
            export_prefix: Optional prefix for exported filenames.
            export_suffix: Optional suffix for exported filenames.
        """
        if last_import_directory is not None:
            self._directories.last_import_directory = last_import_directory
        if last_export_directory is not None:
            self._directories.last_export_directory = last_export_directory
        if export_prefix is not None:
            self._directories.export_prefix = export_prefix
        if export_suffix is not None:
            self._directories.export_suffix = export_suffix

    def clear_project(self) -> None:
        """Close all managed sessions and reset the active project state."""
        logger.debug("Clearing project state and open sessions")
        self._app.sm.close_all()
        self._current_project_path = ""
        self._directories = ProjectDirectories()

    def save_project(self, file_path: str) -> ProjectDocument:
        """Capture current sessions and persist them to a project file.

        Args:
            file_path: Destination path for the serialized project document.

        Returns:
            The in-memory document that was written.
        """
        logger.debug("Saving project to {}", file_path)
        project = self._capture_project_document()
        self._store.save(file_path, project)
        self._current_project_path = file_path
        return project

    def load_project(self, file_path: str) -> ProjectLoadReport:
        """Load a project and restore every session whose video is available.

        Args:
            file_path: Path to the project document to read.

        Returns:
            Counts and paths describing restored and skipped sessions.
        """
        logger.debug("Loading project from {}", file_path)
        project = self._store.load(file_path)
        report = self._restore_project_document(project)
        self._current_project_path = file_path
        self._directories = ProjectDirectories(**asdict(project.directories))
        return report

    def _capture_project_document(self) -> ProjectDocument:
        sessions: list[ProjectSessionDocument] = []
        for session in self._app.sm.all_sessions:
            state = session.state
            if state is None:
                continue
            sessions.append(
                ProjectSessionDocument(
                    video_path=session.s_id.path,
                    current_frame_index=state.playback.current_frame_index,
                    next_annotation_id=state.next_annotation_id,
                    settings=asdict(state.settings),
                    layers=session.data.to_project_payload(),
                )
            )

        active_session = self._app.active_session_id
        return ProjectDocument(
            active_session_path=active_session.path if active_session else "",
            directories=ProjectDirectories(
                last_import_directory=self._directories.last_import_directory,
                last_export_directory=self._directories.last_export_directory,
                export_prefix=self._directories.export_prefix,
                export_suffix=self._directories.export_suffix,
            ),
            sessions=sessions,
        )

    def _restore_project_document(self, project: ProjectDocument) -> ProjectLoadReport:
        self._app.sm.close_all()
        restored_session_paths: set[str] = set()
        skipped_session_paths: list[str] = []
        for entry in project.sessions:
            if not os.path.exists(entry.video_path):
                skipped_session_paths.append(entry.video_path)
                logger.warning("Skipping missing project video '{}'", entry.video_path)
                continue
            try:
                self._app.open_video_from_path(entry.video_path)
                session = self._app.get_session_by_id(SessionId(entry.video_path))
                session.state.settings = self._deserialize_settings(entry.video_path, entry.settings)
                session.state.playback.current_frame_index = max(0, entry.current_frame_index)
                session.state.next_annotation_id = max(1, entry.next_annotation_id)
                session.data.load_project_payload(entry.layers)
                restored_session_paths.add(entry.video_path)
            except Exception as exc:
                self._app.sm.discard_session(SessionId(entry.video_path))
                skipped_session_paths.append(entry.video_path)
                logger.warning("Skipping project session '{}' after restore failure: {}", entry.video_path, exc)

        if project.active_session_path and project.active_session_path in restored_session_paths:
            self._app.active_session_id = SessionId(project.active_session_path)
        elif restored_session_paths:
            self._app.initialize_active_session()
        logger.trace(
            "Project restore complete: requested_sessions={} restored_sessions={} skipped_sessions={}",
            len(project.sessions),
            len(restored_session_paths),
            len(skipped_session_paths),
        )
        return ProjectLoadReport(
            restored_sessions=len(restored_session_paths),
            skipped_session_paths=skipped_session_paths,
        )

    def _deserialize_settings(self, video_path: str, raw_settings: dict[str, object]) -> ProcessingSettings:
        supported_keys = ProcessingSettings.__dataclass_fields__.keys()
        filtered_settings = {key: value for key, value in raw_settings.items() if key in supported_keys}
        ignored_keys = sorted(key for key in raw_settings if key not in supported_keys)
        if ignored_keys:
            logger.warning(
                "Ignoring unsupported project settings for '{}': {}",
                video_path,
                ", ".join(ignored_keys),
            )
        return ProcessingSettings(**filtered_settings)
