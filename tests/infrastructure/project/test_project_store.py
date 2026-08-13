from __future__ import annotations

import pytest

from app.domain.project import ProjectDirectories, ProjectDocument, ProjectSessionDocument
from app.infrastructure.project import ProjectStore
from app.shared.exceptions import ProjectFormatException


class TestProjectStore:
    def test_save_and_load_round_trip(self, tmp_path) -> None:
        store = ProjectStore()
        project_path = tmp_path / "sample.blurzy"
        document = ProjectDocument(
            active_session_path="/videos/a.mp4",
            directories=ProjectDirectories(
                last_import_directory="/imports",
                last_export_directory="/exports",
                export_prefix="pre_",
                export_suffix="_suf",
            ),
            sessions=[
                ProjectSessionDocument(
                    video_path="/videos/a.mp4",
                    current_frame_index=12,
                    next_annotation_id=5,
                    settings={"detection_model_name": "None"},
                    layers={"b": {"12": [{"id": "1", "source": "Manual", "label": "person", "bbox_xyxy": [1, 2, 3, 4], "color_hex": "#00ff00", "confidence": None, "key": "k1"}]}},
                )
            ],
        )

        store.save(str(project_path), document)
        loaded = store.load(str(project_path))

        assert loaded.active_session_path == "/videos/a.mp4"
        assert loaded.directories.last_import_directory == "/imports"
        assert loaded.directories.export_prefix == "pre_"
        assert loaded.sessions[0].current_frame_index == 12
        assert loaded.sessions[0].layers["b"]["12"][0]["key"] == "k1"

    def test_load_rejects_unsupported_format_version(self, tmp_path) -> None:
        project_path = tmp_path / "bad.blurzy"
        project_path.write_text('{"format_version":"9.9","sessions":[]}', encoding="utf-8")

        with pytest.raises(ProjectFormatException):
            ProjectStore().load(str(project_path))
