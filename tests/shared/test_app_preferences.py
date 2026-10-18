from __future__ import annotations

from app.shared.app_preferences import AppPreferences, AppPreferencesStore


class _FakeSettings:
    def __init__(self, initial: dict[str, object] | None = None) -> None:
        self._values = dict(initial or {})
        self.synced = False

    def value(self, key: str, defaultValue: object | None = None) -> object:
        return self._values.get(key, defaultValue)

    def setValue(self, key: str, value: object) -> None:
        self._values[key] = value

    def sync(self) -> None:
        self.synced = True


class TestAppPreferencesStore:
    def test_load_uses_defaults_when_store_is_empty(self) -> None:
        preferences = AppPreferencesStore(_FakeSettings()).load()

        assert preferences.startup_fullscreen is False
        assert preferences.default_detection_model_name == "None"
        assert preferences.default_chosen_labels == ["person", "cat", "dog"]
        assert preferences.default_reid_embedding_dim == 256
        assert preferences.last_project_directory == ""
        assert preferences.default_export_suffix == "_exported"

    def test_load_coerces_saved_values(self) -> None:
        store = AppPreferencesStore(
            _FakeSettings(
                {
                    "preferences/startup_fullscreen": "true",
                    "preferences/default_min_detection_confidence": "0.55",
                    "preferences/default_chosen_labels": "person, car , bike",
                    "preferences/default_blur_enabled": "1",
                    "preferences/default_reid_embedding_dim": "512",
                    "preferences/default_export_directory": "/tmp/out",
                }
            )
        )

        preferences = store.load()

        assert preferences.startup_fullscreen is True
        assert preferences.default_min_detection_confidence == 0.55
        assert preferences.default_chosen_labels == ["person", "car", "bike"]
        assert preferences.default_blur_enabled is True
        assert preferences.default_reid_embedding_dim == 512
        assert preferences.default_export_directory == "/tmp/out"

    def test_save_persists_round_trip_values(self) -> None:
        fake_settings = _FakeSettings()
        store = AppPreferencesStore(fake_settings)
        preferences = AppPreferences(
            startup_fullscreen=True,
            default_detection_model_name="yolov8n",
            default_chosen_labels=["person", "face"],
            default_offline_stitching_enabled=False,
            default_max_stitch_gap=45,
            default_reid_embedding_dim=128,
            default_gsi_smoothness=12.5,
            default_box_border_width=5,
            default_show_preview_mask=True,
            default_preview_blur_enabled=True,
            last_project_directory="/projects",
            default_export_directory="/exports",
            default_export_prefix="final_",
            default_export_suffix="_done",
        )

        store.save(preferences)
        loaded = store.load()

        assert fake_settings.synced is True
        assert loaded.startup_fullscreen is True
        assert loaded.default_detection_model_name == "yolov8n"
        assert loaded.default_chosen_labels == ["person", "face"]
        assert loaded.default_offline_stitching_enabled is False
        assert loaded.default_max_stitch_gap == 45
        assert loaded.default_reid_embedding_dim == 128
        assert loaded.default_gsi_smoothness == 12.5
        assert loaded.default_box_border_width == 5
        assert loaded.default_show_preview_mask is True
        assert loaded.default_preview_blur_enabled is True
        assert loaded.to_processing_settings_kwargs()["max_stitch_gap"] == 45
        assert loaded.to_processing_settings_kwargs()["reid_embedding_dim"] == 128
        assert loaded.last_project_directory == "/projects"
        assert loaded.default_export_directory == "/exports"
        assert loaded.default_export_prefix == "final_"
        assert loaded.default_export_suffix == "_done"
