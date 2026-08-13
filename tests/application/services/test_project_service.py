from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path
import sys
import types
from types import SimpleNamespace

_SRC_ROOT = str(Path(__file__).resolve().parents[3] / "src" / "app")


def _package(name: str, path: str) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__path__ = [path]
    return module


sys.modules.setdefault("app", _package("app", _SRC_ROOT))
sys.modules.setdefault("app.application", _package("app.application", f"{_SRC_ROOT}/application"))
sys.modules.setdefault(
    "app.application.services",
    _package("app.application.services", f"{_SRC_ROOT}/application/services"),
)
sys.modules.setdefault("app.infrastructure", _package("app.infrastructure", f"{_SRC_ROOT}/infrastructure"))
sys.modules.setdefault(
    "app.infrastructure.session",
    _package("app.infrastructure.session", f"{_SRC_ROOT}/infrastructure/session"),
)

class _QObjectStub:
    def __init__(self, *args, **kwargs):
        pass


_qtcore_module = sys.modules.get("PySide6.QtCore")
if _qtcore_module is not None:
    _qtcore_module.QObject = _QObjectStub

for _module_name in (
    "app.infrastructure.session.session_data_store",
    "app.infrastructure.session.session",
    "app.application.services.project_service",
):
    _module = sys.modules.get(_module_name)
    if _module is not None:
        importlib.reload(_module)

from app.application.services.project_service import ProjectService
from app.domain import VideoDataLayer
from app.domain.export import ProcessingSettings
from app.domain.session import SessionId
from app.infrastructure.session.session_data_store import SessionDataStore


@dataclass
class _FakeSession:
    s_id: SessionId
    state: object
    data: SessionDataStore


class _FakeSessionManager:
    def __init__(self, sessions: list[_FakeSession] | None = None) -> None:
        self._sessions = {session.s_id: session for session in sessions or []}

    @property
    def all_sessions(self):
        return list(self._sessions.values())

    def close_all(self) -> None:
        self._sessions.clear()

    def add(self, session: _FakeSession) -> None:
        self._sessions[session.s_id] = session


class _FakeApp:
    def __init__(self, sessions: list[_FakeSession] | None = None) -> None:
        self.sm = _FakeSessionManager(sessions)
        self._active_session_id = sessions[0].s_id if sessions else None

    @property
    def active_session_id(self):
        return self._active_session_id

    @active_session_id.setter
    def active_session_id(self, value):
        self._active_session_id = value

    def open_video_from_path(self, path: str) -> None:
        data = SessionDataStore(s_id=SessionId(path))
        state = SimpleNamespace(
            playback=SimpleNamespace(current_frame_index=0),
            next_annotation_id=1,
            settings=ProcessingSettings(),
        )
        self.sm.add(_FakeSession(SessionId(path), state, data))

    def get_session_by_id(self, s_id: SessionId) -> _FakeSession:
        return self.sm._sessions[s_id]

    def initialize_active_session(self) -> None:
        sessions = self.sm.all_sessions
        self._active_session_id = sessions[0].s_id if sessions else None


def _make_session(path: str) -> _FakeSession:
    data = SessionDataStore(s_id=SessionId(path))
    data.add_box_to_layer_at_frame_index(
        VideoDataLayer.B,
        7,
        SimpleNamespace(
            id="ann-1",
            source=SimpleNamespace(value="Manual"),
            label="person",
            bbox_xyxy=(1, 2, 3, 4),
            color_hex="#00ff00",
            confidence=None,
            key="box-1",
        ),
    )
    state = SimpleNamespace(
        playback=SimpleNamespace(current_frame_index=7),
        next_annotation_id=3,
        settings=ProcessingSettings(),
    )
    return _FakeSession(SessionId(path), state, data)


class TestProjectService:
    def test_save_and_load_round_trip(self, tmp_path) -> None:
        video_path = tmp_path / "video.mp4"
        video_path.write_text("stub", encoding="utf-8")
        session = _make_session(str(video_path))
        app = _FakeApp([session])
        service = ProjectService(app)
        service.update_directories(
            last_import_directory="/imports",
            last_export_directory="/exports",
            export_prefix="pre_",
            export_suffix="_done",
        )
        project_path = tmp_path / "demo.blurzy"

        service.save_project(str(project_path))

        restored_app = _FakeApp()
        restored = ProjectService(restored_app)
        report = restored.load_project(str(project_path))

        restored_session = restored_app.get_session_by_id(SessionId(str(video_path)))
        assert report.restored_sessions == 1
        assert report.skipped_missing_paths == []
        assert restored.current_project_path == str(project_path)
        assert restored.directories.last_export_directory == "/exports"
        assert restored_session.state.playback.current_frame_index == 7
        assert restored_session.state.next_annotation_id == 3
        boxes = restored_session.data.get_boxes_for_layer_at_frame_index_as_list(VideoDataLayer.B, 7)
        assert len(boxes) == 1
        assert boxes[0].key == "box-1"

    def test_load_skips_missing_video_assets_and_restores_available_sessions(self, tmp_path) -> None:
        app = _FakeApp()
        service = ProjectService(app)
        existing_video_path = tmp_path / "video.mp4"
        existing_video_path.write_text("stub", encoding="utf-8")
        project_path = tmp_path / "partial.blurzy"
        project_path.write_text(
            (
                '{"format_version":"1.0","active_session_path":"/nope/video.mp4","directories":{},'
                '"sessions":[{"video_path":"/nope/video.mp4","current_frame_index":0,"next_annotation_id":1,'
                '"settings":{},"layers":{}},{"video_path":"'
                f'{existing_video_path}'
                '","current_frame_index":0,"next_annotation_id":1,"settings":{},"layers":{}}]}'
            ),
            encoding="utf-8",
        )

        report = service.load_project(str(project_path))

        assert report.restored_sessions == 1
        assert report.skipped_missing_paths == ["/nope/video.mp4"]
        assert app.active_session_id == SessionId(str(existing_video_path))

    def test_load_ignores_unknown_saved_setting_keys(self, tmp_path) -> None:
        app = _FakeApp()
        service = ProjectService(app)
        video_path = tmp_path / "video.mp4"
        video_path.write_text("stub", encoding="utf-8")
        project_path = tmp_path / "future.blurzy"
        project_path.write_text(
            (
                '{"format_version":"1.0","active_session_path":"","directories":{},'
                '"sessions":[{"video_path":"'
                f'{video_path}'
                '","current_frame_index":0,"next_annotation_id":1,'
                '"settings":{"detection_model_name":"demo","future_toggle":true},"layers":{}}]}'
            ),
            encoding="utf-8",
        )

        report = service.load_project(str(project_path))

        restored_session = app.get_session_by_id(SessionId(str(video_path)))
        assert report.restored_sessions == 1
        assert restored_session.state.settings.detection_model_name == "demo"
