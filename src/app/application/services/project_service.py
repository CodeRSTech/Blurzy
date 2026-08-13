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
    project: ProjectDocument
    restored_sessions: int
    skipped_missing_paths: list[str]


class ProjectService:
    def __init__(self, app: Application) -> None:
        self._app = app
        self._store = ProjectStore()
        self._current_project_path = ""
        self._directories = ProjectDirectories()

    @property
    def current_project_path(self) -> str:
        return self._current_project_path

    @property
    def directories(self) -> ProjectDirectories:
        return self._directories

    def update_directories(
        self,
        *,
        last_import_directory: str | None = None,
        last_export_directory: str | None = None,
        export_prefix: str | None = None,
        export_suffix: str | None = None,
    ) -> None:
        if last_import_directory is not None:
            self._directories.last_import_directory = last_import_directory
        if last_export_directory is not None:
            self._directories.last_export_directory = last_export_directory
        if export_prefix is not None:
            self._directories.export_prefix = export_prefix
        if export_suffix is not None:
            self._directories.export_suffix = export_suffix

    def clear_project(self) -> None:
        logger.debug("Clearing project state and open sessions")
        self._app.sm.close_all()
        self._current_project_path = ""
        self._directories = ProjectDirectories()

    def save_project(self, file_path: str) -> ProjectDocument:
        logger.debug("Saving project to {}", file_path)
        project = self._capture_project_document()
        self._store.save(file_path, project)
        self._current_project_path = file_path
        return project

    def load_project(self, file_path: str) -> ProjectLoadReport:
        logger.debug("Loading project from {}", file_path)
        project = self._store.load(file_path)
        report = self._restore_project_document(project)
        self._current_project_path = file_path
        self._directories = project.directories
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
        skipped_missing_paths: list[str] = []
        for entry in project.sessions:
            if not os.path.exists(entry.video_path):
                skipped_missing_paths.append(entry.video_path)
                logger.warning("Skipping missing project video '{}'", entry.video_path)
                continue
            self._app.open_video_from_path(entry.video_path)
            session = self._app.get_session_by_id(SessionId(entry.video_path))
            session.state.settings = ProcessingSettings(**entry.settings)
            session.state.playback.current_frame_index = max(0, entry.current_frame_index)
            session.state.next_annotation_id = max(1, entry.next_annotation_id)
            session.data.load_project_payload(entry.layers)
            restored_session_paths.add(entry.video_path)

        if project.active_session_path and project.active_session_path in restored_session_paths:
            self._app.active_session_id = SessionId(project.active_session_path)
        elif restored_session_paths:
            self._app.initialize_active_session()
        logger.trace(
            "Project restore complete: requested_sessions={} restored_sessions={} skipped_missing_sessions={}",
            len(project.sessions),
            len(restored_session_paths),
            len(skipped_missing_paths),
        )
        return ProjectLoadReport(
            project=project,
            restored_sessions=len(restored_session_paths),
            skipped_missing_paths=skipped_missing_paths,
        )
