"""Unit tests for DetectionEngineManager — create / update / remove semantics."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.application.managers.detection_engine import DetectionEngineManager
from app.infrastructure.adapters.detection_engine_adapter import DetectionEngineAdapter


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_session_repo(detection_engine=None):
    """Return a mock SessionRepositoryInterface whose session has the given engine."""
    session = MagicMock()
    session.detection_engine = detection_engine

    repo = MagicMock()
    repo.get_session_by_id.return_value = session
    return repo, session


# ---------------------------------------------------------------------------
# create_or_update — engine is None → should CREATE a new DetectionEngine
# wrapped in a DetectionEngineAdapter (Pattern B)
# ---------------------------------------------------------------------------

class TestCreateOrUpdateCreatesEngine:
    """When a session has no engine, create_or_update should instantiate one
    via the factory, which wraps it in a DetectionEngineAdapter."""

    def test_creates_new_engine_when_none_exists(self):
        repo, session = _make_session_repo(detection_engine=None)
        fake_engine = MagicMock(name="FakeDetectionEngine")

        with patch(
            "app.infrastructure.detection.engine.detection_engine_factory.DetectionEngine",
            return_value=fake_engine,
        ) as MockEngine:
            manager = DetectionEngineManager(repo)
            s_id = MagicMock()
            manager.create_or_update(s_id, "YOLOv8n")

        MockEngine.assert_called_once_with("YOLOv8n")
        # Factory now wraps the raw engine in a DetectionEngineAdapter (Pattern B)
        assert isinstance(session.detection_engine, DetectionEngineAdapter)
        assert session.detection_engine._engine is fake_engine

    def test_passes_model_name_to_constructor(self):
        repo, session = _make_session_repo(detection_engine=None)

        with patch(
            "app.infrastructure.detection.engine.detection_engine_factory.DetectionEngine"
        ) as MockEngine:
            manager = DetectionEngineManager(repo)
            s_id = MagicMock()
            manager.create_or_update(s_id, "YOLO11m")

        MockEngine.assert_called_once_with("YOLO11m")


# ---------------------------------------------------------------------------
# create_or_update — engine already exists → should UPDATE via set_model
# ---------------------------------------------------------------------------

class TestCreateOrUpdateUpdatesEngine:
    """When a session already has an engine, create_or_update should call set_model."""

    def test_calls_set_model_when_engine_exists(self):
        existing_engine = MagicMock(name="ExistingEngine")
        repo, session = _make_session_repo(detection_engine=existing_engine)

        manager = DetectionEngineManager(repo)
        s_id = MagicMock()
        manager.create_or_update(s_id, "yolov8s")

        existing_engine.set_model.assert_called_once_with("yolov8s")

    def test_does_not_replace_existing_engine_instance(self):
        existing_engine = MagicMock(name="ExistingEngine")
        repo, session = _make_session_repo(detection_engine=existing_engine)

        with patch(
            "app.infrastructure.detection.engine.detection_engine_factory.DetectionEngine"
        ) as MockEngine:
            manager = DetectionEngineManager(repo)
            s_id = MagicMock()
            manager.create_or_update(s_id, "yolov8s")

        MockEngine.assert_not_called()
        assert session.detection_engine is existing_engine

    def test_passes_new_model_name_to_set_model(self):
        existing_engine = MagicMock(name="ExistingEngine")
        repo, session = _make_session_repo(detection_engine=existing_engine)

        manager = DetectionEngineManager(repo)
        s_id = MagicMock()
        manager.create_or_update(s_id, "yolov8x")

        existing_engine.set_model.assert_called_once_with("yolov8x")


# ---------------------------------------------------------------------------
# remove — should clear detection_engine to None
# ---------------------------------------------------------------------------

class TestRemoveEngine:
    """remove() should set session.detection_engine to None."""

    def test_sets_detection_engine_to_none(self):
        existing_engine = MagicMock(name="ExistingEngine")
        repo, session = _make_session_repo(detection_engine=existing_engine)

        manager = DetectionEngineManager(repo)
        s_id = MagicMock()
        manager.remove(s_id)

        assert session.detection_engine is None

    def test_remove_when_engine_already_none_does_not_raise(self):
        repo, session = _make_session_repo(detection_engine=None)

        manager = DetectionEngineManager(repo)
        s_id = MagicMock()

        # Should not raise
        manager.remove(s_id)

        assert session.detection_engine is None

    def test_remove_uses_correct_session_id(self):
        existing_engine = MagicMock()
        repo, session = _make_session_repo(detection_engine=existing_engine)

        manager = DetectionEngineManager(repo)
        s_id = MagicMock()
        manager.remove(s_id)

        repo.get_session_by_id.assert_called_once_with(s_id)


# ---------------------------------------------------------------------------
# repo delegation
# ---------------------------------------------------------------------------

class TestSessionRepoDelegation:
    """Manager must always delegate session lookup to the repository."""

    def test_create_or_update_fetches_session_by_id(self):
        repo, session = _make_session_repo(detection_engine=None)

        with patch("app.infrastructure.detection.engine.detection_engine_factory.DetectionEngine"):
            manager = DetectionEngineManager(repo)
            s_id = MagicMock()
            manager.create_or_update(s_id, "YOLOv8n")

        repo.get_session_by_id.assert_called_once_with(s_id)

    def test_remove_fetches_session_by_id(self):
        repo, session = _make_session_repo(detection_engine=None)

        manager = DetectionEngineManager(repo)
        s_id = MagicMock()
        manager.remove(s_id)

        repo.get_session_by_id.assert_called_once_with(s_id)
