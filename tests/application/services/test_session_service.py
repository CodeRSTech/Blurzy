"""Unit tests for SessionService — delegation, settings validation, and playback flows.

Note on test setup:
    ``SessionService`` inherits from ``QObject``.  In the test environment
    ``conftest.py`` replaces ``PySide6.QtCore`` with a ``MagicMock`` stub so
    that ``QObject`` is a mock object.  Inheriting from a MagicMock turns the
    entire class into a MagicMock, preventing real method execution.

    To avoid this, we override ``PySide6.QtCore.QObject`` with a lightweight
    real class **before** ``session_service`` is imported.  The override is
    scoped to the ``sys.modules`` entry already created by conftest — it does
    not change any other module behaviour.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Patch QObject BEFORE importing session_service so the class body executes
# normally.  conftest.py has already installed a MagicMock for PySide6.QtCore;
# we replace just the QObject attribute with a real stub class.
# ---------------------------------------------------------------------------
import importlib
import sys


class _QObjectStub:
    """Minimal real base-class substitute for ``QObject`` in unit tests.

    **Why this is needed:**

    ``conftest.py`` replaces the entire ``PySide6.QtCore`` module with a
    ``MagicMock``.  Any class that inherits from ``QObject`` (a child mock of
    that module) ends up inheriting from a ``MagicMock`` instance.  Python's
    ``MagicMock.__mro_entries__`` causes the derived class itself to become a
    ``MagicMock``, which means all instances are mocks and method bodies are
    never executed.

    Replacing ``QObject`` with this lightweight real class before importing
    ``SessionService`` ensures that the class body is executed normally and
    instances behave as plain Python objects.
    """

    def __init__(self, *args, **kwargs):
        pass


_qtcore_module = sys.modules.get("PySide6.QtCore")
if _qtcore_module is not None:
    _qtcore_module.QObject = _QObjectStub

# Reload session_service so it picks up our QObject stub if it was already
# imported (importlib.reload is safer than deleting the sys.modules entry).
_SESSION_SVC_KEY = "app.application.services.session_service"
_session_svc_module = sys.modules.get(_SESSION_SVC_KEY)
if _session_svc_module is not None:
    importlib.reload(_session_svc_module)

# ---------------------------------------------------------------------------
# Normal imports (SessionService is imported with the real QObject stub above)
# ---------------------------------------------------------------------------
import types
from unittest.mock import MagicMock

import pytest

from app.application.services.session_service import SessionService, _is_settings_type_compatible
from app.shared.exceptions import (
    SessionAlreadyExistsException,
    NoNewOpenedSessionsException,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_app(
    active_session_id=None,
    session=None,
):
    """Return a minimal mock App object for SessionService tests."""
    app = MagicMock()

    # SessionService uses ApplicationAdapter, which delegates through ``app.sm``.
    sm = MagicMock()
    app.sm = sm
    sm.active_session_id = active_session_id

    # Keep the old assertion surface stable by aliasing app-level mocks to sm-level methods.
    sm.create_session_from_video_path = app.open_video_from_path
    sm.initialize_active_session = app.initialize_active_session
    sm.get_session_by_id = app.get_session_by_id

    if session is not None:
        app.get_session_by_id.return_value = session
    return app


def _make_service(app=None):
    """Return a SessionService with a mock App and a mocked decode-worker manager.

    With the QObject stub in place, SessionService is now a real Python class
    and instances are plain objects, so attribute reads/writes behave normally.
    We replace ``_decode_worker_manager`` with a MagicMock after construction so
    that worker-lifecycle calls can be asserted without real workers.
    """
    if app is None:
        app = _make_app()
    service = SessionService(app)
    service._decode_worker_manager = MagicMock()
    return service


# ---------------------------------------------------------------------------
# _is_settings_type_compatible (module-level helper)
# ---------------------------------------------------------------------------

class TestIsSettingsTypeCompatible:
    """Type-compatibility checks for the settings validation helper."""

    def test_same_type_float(self):
        assert _is_settings_type_compatible(1.0, 2.5) is True

    def test_same_type_str(self):
        assert _is_settings_type_compatible("a", "b") is True

    def test_same_type_bool(self):
        assert _is_settings_type_compatible(True, False) is True

    def test_same_type_list(self):
        assert _is_settings_type_compatible(["x"], ["y", "z"]) is True

    def test_int_for_float_field_is_compatible(self):
        # UI sliders may emit int; float fields must accept them
        assert _is_settings_type_compatible(1.0, 5) is True

    def test_bool_for_float_field_is_not_compatible(self):
        # bool is a subclass of int; it should NOT widen into a float field
        assert _is_settings_type_compatible(1.0, True) is False

    def test_str_for_float_field_is_not_compatible(self):
        assert _is_settings_type_compatible(1.0, "0.5") is False

    def test_str_for_bool_field_is_not_compatible(self):
        assert _is_settings_type_compatible(True, "true") is False

    def test_int_for_bool_field_is_not_compatible(self):
        # Integers should NOT silently become booleans
        assert _is_settings_type_compatible(True, 1) is False

    def test_float_for_int_field_is_not_compatible(self):
        assert _is_settings_type_compatible(3, 2.5) is False


# ---------------------------------------------------------------------------
# handle_active_session_changed — delegation to VideoDecodeWorkerManager
# ---------------------------------------------------------------------------

class TestHandleActiveSessionChanged:
    """Ensure handle_active_session_changed delegates fully to the manager."""

    def test_delegates_to_switch_active_session(self):
        service = _make_service()
        old_id = MagicMock()
        new_id = MagicMock()

        service.handle_active_session_changed(old_id, new_id)

        service._decode_worker_manager.switch_active_session.assert_called_once_with(
            old_s_id=old_id, new_s_id=new_id
        )

    def test_delegates_with_none_old_id(self):
        service = _make_service()
        new_id = MagicMock()

        service.handle_active_session_changed(None, new_id)

        service._decode_worker_manager.switch_active_session.assert_called_once_with(
            old_s_id=None, new_s_id=new_id
        )

    def test_no_direct_worker_manipulation(self):
        """SessionService must not call activate/deactivate directly."""
        service = _make_service()

        service.handle_active_session_changed(MagicMock(), MagicMock())

        service._decode_worker_manager.activate.assert_not_called()
        service._decode_worker_manager.deactivate.assert_not_called()


# ---------------------------------------------------------------------------
# open_videos — delegation and error handling
# ---------------------------------------------------------------------------

class TestOpenVideos:
    """open_videos should iterate paths, skip duplicates, and raise when nothing opened."""

    def test_returns_newly_opened_paths(self):
        app = _make_app(active_session_id="some_id")
        service = _make_service(app)

        result = service.open_videos(["/a/video.mp4", "/b/other.mp4"])

        assert result == ["/a/video.mp4", "/b/other.mp4"]
        assert app.open_video_from_path.call_count == 2

    def test_skips_duplicate_paths(self):
        app = _make_app(active_session_id="some_id")
        app.open_video_from_path.side_effect = [
            None,
            SessionAlreadyExistsException("dup", "/b/video.mp4"),
        ]
        service = _make_service(app)

        result = service.open_videos(["/a/video.mp4", "/b/video.mp4"])

        assert result == ["/a/video.mp4"]

    def test_raises_when_all_paths_are_duplicates(self):
        app = _make_app(active_session_id="some_id")
        app.open_video_from_path.side_effect = SessionAlreadyExistsException("dup", "/a.mp4")
        service = _make_service(app)

        with pytest.raises(NoNewOpenedSessionsException):
            service.open_videos(["/a.mp4"])

    def test_initializes_active_session_when_none_active(self):
        app = _make_app(active_session_id=None)
        service = _make_service(app)

        service.open_videos(["/a/video.mp4"])

        app.initialize_active_session.assert_called_once()

    def test_does_not_initialize_active_session_when_already_active(self):
        app = _make_app(active_session_id="existing")
        service = _make_service(app)

        service.open_videos(["/a/video.mp4"])

        app.initialize_active_session.assert_not_called()


# ---------------------------------------------------------------------------
# start_session_playback — delegates via Session.is_playing_video property
# ---------------------------------------------------------------------------

class TestStartSessionPlayback:
    """start_session_playback should set is_playing_video on the Session."""

    def test_sets_is_playing_video_true(self):
        session = MagicMock()
        session.is_playing_video = False
        app = _make_app(session=session)
        service = _make_service(app)
        s_id = MagicMock()

        service.start_session_playback(s_id)

        assert session.is_playing_video is True

    def test_fetches_correct_session_by_id(self):
        session = MagicMock()
        app = _make_app(session=session)
        service = _make_service(app)
        s_id = MagicMock()

        service.start_session_playback(s_id)

        app.get_session_by_id.assert_called_once_with(s_id)


# ---------------------------------------------------------------------------
# session_by_id_has_buffered_frame — delegates to Session property
# ---------------------------------------------------------------------------

class TestSessionByIdHasBufferedFrame:

    def test_returns_true_when_buffered(self):
        session = MagicMock()
        session.has_buffered_frame = True
        service = _make_service(_make_app(session=session))

        result = service.session_by_id_has_buffered_frame(MagicMock())

        assert result is True

    def test_returns_false_when_not_buffered(self):
        session = MagicMock()
        session.has_buffered_frame = False
        service = _make_service(_make_app(session=session))

        result = service.session_by_id_has_buffered_frame(MagicMock())

        assert result is False


# ---------------------------------------------------------------------------
# session_by_id_has_running_detection_worker
# ---------------------------------------------------------------------------

class TestSessionByIdHasRunningDetectionWorker:

    def test_delegates_to_session_property_true(self):
        session = MagicMock()
        session.has_running_detection_worker = True
        service = _make_service(_make_app(session=session))

        result = service.session_by_id_has_running_detection_worker(MagicMock())

        assert result is True

    def test_delegates_to_session_property_false(self):
        session = MagicMock()
        session.has_running_detection_worker = False
        service = _make_service(_make_app(session=session))

        result = service.session_by_id_has_running_detection_worker(MagicMock())

        assert result is False


# ---------------------------------------------------------------------------
# session_by_id_has_running_tracking_worker
# ---------------------------------------------------------------------------

class TestSessionByIdHasRunningTrackingWorker:

    def test_delegates_to_session_property_true(self):
        session = MagicMock()
        session.has_running_tracking_worker = True
        service = _make_service(_make_app(session=session))

        result = service.session_by_id_has_running_tracking_worker(MagicMock())

        assert result is True

    def test_delegates_to_session_property_false(self):
        session = MagicMock()
        session.has_running_tracking_worker = False
        service = _make_service(_make_app(session=session))

        result = service.session_by_id_has_running_tracking_worker(MagicMock())

        assert result is False


# ---------------------------------------------------------------------------
# update_session_settings — valid keys, unknown keys, type mismatches
# ---------------------------------------------------------------------------

def _make_settings(**initial):
    """Build a SimpleNamespace with typed real attributes for update tests.

    Attribute types mirror ``ProcessingSettings`` defaults, including
    ``detection_model_name="None"`` (the string ``"None"``, not Python's
    ``None``) which is the sentinel value used by ``ProcessingSettings`` to
    indicate that no detection model is selected.
    """
    defaults = dict(
        blur_strength=15.0,
        blur_enabled=False,
        draw_boxes=True,
        min_detection_confidence=0.25,
        # "None" (string) is the sentinel used by ProcessingSettings when
        # no model is selected — matches the production default exactly.
        detection_model_name="None",
    )
    defaults.update(initial)
    return types.SimpleNamespace(**defaults)


class TestUpdateSessionSettings:
    """update_session_settings: valid updates, unknown-key skip, type-mismatch skip."""

    def _service_with_settings(self, settings):
        session = MagicMock()
        session.state.settings = settings
        app = _make_app(session=session)
        return _make_service(app)

    # --- valid updates ---

    def test_applies_valid_float_update(self):
        settings = _make_settings(blur_strength=15.0)
        service = self._service_with_settings(settings)

        service.update_session_settings(MagicMock(), blur_strength=25.0)

        assert settings.blur_strength == 25.0

    def test_applies_int_to_float_field(self):
        """int → float is an accepted numeric widening."""
        settings = _make_settings(blur_strength=15.0)
        service = self._service_with_settings(settings)

        service.update_session_settings(MagicMock(), blur_strength=20)

        assert settings.blur_strength == 20

    def test_applies_bool_update(self):
        settings = _make_settings(blur_enabled=False)
        service = self._service_with_settings(settings)

        service.update_session_settings(MagicMock(), blur_enabled=True)

        assert settings.blur_enabled is True

    def test_applies_multiple_valid_settings(self):
        settings = _make_settings(blur_strength=15.0, draw_boxes=True)
        service = self._service_with_settings(settings)

        service.update_session_settings(
            MagicMock(), blur_strength=30.0, draw_boxes=False
        )

        assert settings.blur_strength == 30.0
        assert settings.draw_boxes is False

    # --- unknown key ---

    def test_skips_unknown_key(self):
        settings = _make_settings()
        service = self._service_with_settings(settings)

        # Should NOT raise, and must not add the unknown key
        service.update_session_settings(MagicMock(), nonexistent_key="hello")

        assert not hasattr(settings, "nonexistent_key")

    def test_valid_and_unknown_keys_mixed(self):
        """Valid keys are still applied even when an unknown key is present."""
        settings = _make_settings(blur_strength=15.0)
        service = self._service_with_settings(settings)

        service.update_session_settings(
            MagicMock(), blur_strength=20.0, totally_wrong_key=99
        )

        assert settings.blur_strength == 20.0
        assert not hasattr(settings, "totally_wrong_key")

    # --- type mismatch ---

    def test_skips_string_for_float_field(self):
        settings = _make_settings(blur_strength=15.0)
        service = self._service_with_settings(settings)

        service.update_session_settings(MagicMock(), blur_strength="fast")

        # Value must be unchanged
        assert settings.blur_strength == 15.0

    def test_skips_string_for_bool_field(self):
        settings = _make_settings(draw_boxes=True)
        service = self._service_with_settings(settings)

        service.update_session_settings(MagicMock(), draw_boxes="yes")

        assert settings.draw_boxes is True

    def test_skips_float_for_bool_field(self):
        settings = _make_settings(blur_enabled=False)
        service = self._service_with_settings(settings)

        service.update_session_settings(MagicMock(), blur_enabled=1.0)

        assert settings.blur_enabled is False
