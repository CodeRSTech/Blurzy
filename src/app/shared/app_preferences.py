from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, final


DEFAULT_DETECTION_MODEL_NAME = "None"
DEFAULT_MIN_DETECTION_CONFIDENCE = 0.25
DEFAULT_CHOSEN_LABELS = ["person", "cat", "dog"]
DEFAULT_TRACKING_STRATEGY = "hungarian"
DEFAULT_TRACKING_SOURCE = "b"
DEFAULT_REID_EMBEDDING_DIM = 256
DEFAULT_MIN_IOU = 0.3
DEFAULT_MIN_TRACKER_CONFIDENCE = 0.1
DEFAULT_CONFIDENCE_DECAY = 0.05
DEFAULT_OFFLINE_STITCHING_ENABLED = True
DEFAULT_MAX_STITCH_GAP = 25
DEFAULT_GSI_SMOOTHNESS = 10.0
DEFAULT_DRAW_BOXES = True
DEFAULT_BOX_BORDER_WIDTH = 2
DEFAULT_SHOW_PREVIEW_MASK = False
DEFAULT_PREVIEW_BLUR_ENABLED = False
DEFAULT_BLUR_ENABLED = False
DEFAULT_BLUR_STRENGTH = 15.0


def _parse_labels(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _coerce_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _coerce_float(value: object, default: float) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return default
    return default


def _coerce_int(value: object, default: int) -> int:
    """Convert a stored value to an integer, falling back for invalid input.

    Args:
        value: Raw QSettings value.
        default: Fallback used for unsupported or malformed values.

    Returns:
        An integer suitable for a discrete preference.

    Note:
        Booleans are excluded even though Python treats them as integers.

    Example:
        frames = _coerce_int("25", 25)
    """
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return default
    return default


def _coerce_reid_embedding_dim(value: object, default: int) -> int:
    """Load a persisted embedding size or fall back to a supported default.

    Args:
        value: Raw preference value.
        default: Supported fallback dimension.

    Returns:
        One of the supported embedding dimensions.
    """
    candidate = _coerce_int(value, default)
    return candidate if candidate in (128, 256, 512) else default


def _coerce_str(value: object, default: str) -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    return str(value)


class _SettingsBackend(Protocol):
    def value(self, key: str, defaultValue: object | None = None) -> object: ...

    def setValue(self, key: str, value: object) -> None: ...

    def sync(self) -> None: ...


@dataclass(slots=True)
class AppPreferences:
    """Persisted application defaults and last-used locations.

    Note:
        Default processing options are copied into sessions when they are created;
        edits to a session do not mutate these global preferences.
    """
    startup_fullscreen: bool = False
    default_detection_model_name: str = DEFAULT_DETECTION_MODEL_NAME
    default_min_detection_confidence: float = DEFAULT_MIN_DETECTION_CONFIDENCE
    default_chosen_labels: list[str] = field(default_factory=lambda: list(DEFAULT_CHOSEN_LABELS))
    default_tracking_strategy: str = DEFAULT_TRACKING_STRATEGY
    default_tracking_source: str = DEFAULT_TRACKING_SOURCE
    default_reid_embedding_dim: int = DEFAULT_REID_EMBEDDING_DIM
    default_min_iou: float = DEFAULT_MIN_IOU
    default_min_tracker_confidence: float = DEFAULT_MIN_TRACKER_CONFIDENCE
    default_confidence_decay: float = DEFAULT_CONFIDENCE_DECAY
    default_offline_stitching_enabled: bool = DEFAULT_OFFLINE_STITCHING_ENABLED
    default_max_stitch_gap: int = DEFAULT_MAX_STITCH_GAP
    default_gsi_smoothness: float = DEFAULT_GSI_SMOOTHNESS
    default_draw_boxes: bool = DEFAULT_DRAW_BOXES
    default_box_border_width: int = DEFAULT_BOX_BORDER_WIDTH
    default_show_preview_mask: bool = DEFAULT_SHOW_PREVIEW_MASK
    default_preview_blur_enabled: bool = DEFAULT_PREVIEW_BLUR_ENABLED
    default_blur_enabled: bool = DEFAULT_BLUR_ENABLED
    default_blur_strength: float = DEFAULT_BLUR_STRENGTH
    last_project_directory: str = ""
    default_export_directory: str = ""
    default_export_prefix: str = ""
    default_export_suffix: str = "_exported"

    @property
    def chosen_labels_text(self) -> str:
        return ", ".join(self.default_chosen_labels)

    def to_processing_settings_kwargs(self) -> dict[str, object]:
        """Map persisted defaults to settings accepted by a new session.


        Returns:
            Processing setting names and values without preference prefixes.


        Note:
            The chosen labels list is copied so a session cannot mutate global defaults.

        Example:
            kwargs = preferences.to_processing_settings_kwargs()
        """
        return {
            "detection_model_name": self.default_detection_model_name,
            "min_detection_confidence": self.default_min_detection_confidence,
            "chosen_labels": list(self.default_chosen_labels),
            "tracking_strategy": self.default_tracking_strategy,
            "tracking_source": self.default_tracking_source,
            "reid_embedding_dim": self.default_reid_embedding_dim,
            "min_iou": self.default_min_iou,
            "min_tracker_confidence": self.default_min_tracker_confidence,
            "confidence_decay": self.default_confidence_decay,
            "offline_stitching_enabled": self.default_offline_stitching_enabled,
            "max_stitch_gap": self.default_max_stitch_gap,
            "gsi_smoothness": self.default_gsi_smoothness,
            "draw_boxes": self.default_draw_boxes,
            "box_border_width": self.default_box_border_width,
            "show_preview_mask": self.default_show_preview_mask,
            "preview_blur_enabled": self.default_preview_blur_enabled,
            "blur_enabled": self.default_blur_enabled,
            "blur_strength": self.default_blur_strength,
        }


@final
class AppPreferencesStore:
    """Load and persist ``AppPreferences`` through a settings backend.

    Note:
        Stored key names are stable across launches and support injected test backends.
    """
    _KEYS = {
        "startup_fullscreen": "preferences/startup_fullscreen",
        "default_detection_model_name": "preferences/default_detection_model_name",
        "default_min_detection_confidence": "preferences/default_min_detection_confidence",
        "default_chosen_labels": "preferences/default_chosen_labels",
        "default_tracking_strategy": "preferences/default_tracking_strategy",
        "default_tracking_source": "preferences/default_tracking_source",
        "default_reid_embedding_dim": "preferences/default_reid_embedding_dim",
        "default_min_iou": "preferences/default_min_iou",
        "default_min_tracker_confidence": "preferences/default_min_tracker_confidence",
        "default_confidence_decay": "preferences/default_confidence_decay",
        "default_offline_stitching_enabled": "preferences/default_offline_stitching_enabled",
        "default_max_stitch_gap": "preferences/default_max_stitch_gap",
        "default_gsi_smoothness": "preferences/default_gsi_smoothness",
        "default_draw_boxes": "preferences/default_draw_boxes",
        "default_box_border_width": "preferences/default_box_border_width",
        "default_show_preview_mask": "preferences/default_show_preview_mask",
        "default_preview_blur_enabled": "preferences/default_preview_blur_enabled",
        "default_blur_enabled": "preferences/default_blur_enabled",
        "default_blur_strength": "preferences/default_blur_strength",
        "last_project_directory": "preferences/last_project_directory",
        "default_export_directory": "preferences/default_export_directory",
        "default_export_prefix": "preferences/default_export_prefix",
        "default_export_suffix": "preferences/default_export_suffix",
    }

    def __init__(self, settings: _SettingsBackend | None = None) -> None:
        """Create a preference store over an injected or Qt settings backend.

        Args:
            settings: Optional backend, defaulting to ``QSettings``.

        Returns:
            None.

        Raises:
            ImportError: If Qt settings are requested but PySide6 is unavailable.

        Note:
            Inject a small backend in tests to avoid persistent machine settings.

        Example:
            store = AppPreferencesStore(fake_settings)
        """
        if settings is None:
            from PySide6.QtCore import QSettings

            settings = QSettings()
        self._settings = settings

    def load(self) -> AppPreferences:
        """Load preferences and coerce raw backend values to field types.


        Returns:
            Preferences populated with saved values or dataclass defaults.


        Note:
            Invalid scalar values fall back to the corresponding current default.

        Example:
            preferences = store.load()
        """
        defaults = AppPreferences()
        return AppPreferences(
            startup_fullscreen=_coerce_bool(
                self._settings.value(self._KEYS["startup_fullscreen"], defaults.startup_fullscreen),
                defaults.startup_fullscreen,
            ),
            default_detection_model_name=_coerce_str(
                self._settings.value(
                    self._KEYS["default_detection_model_name"], defaults.default_detection_model_name
                ),
                defaults.default_detection_model_name,
            ),
            default_min_detection_confidence=_coerce_float(
                self._settings.value(
                    self._KEYS["default_min_detection_confidence"], defaults.default_min_detection_confidence
                ),
                defaults.default_min_detection_confidence,
            ),
            default_chosen_labels=_parse_labels(
                _coerce_str(
                    self._settings.value(self._KEYS["default_chosen_labels"], defaults.chosen_labels_text),
                    defaults.chosen_labels_text,
                )
            ),
            default_tracking_strategy=_coerce_str(
                self._settings.value(self._KEYS["default_tracking_strategy"], defaults.default_tracking_strategy),
                defaults.default_tracking_strategy,
            ),
            default_tracking_source=_coerce_str(
                self._settings.value(self._KEYS["default_tracking_source"], defaults.default_tracking_source),
                defaults.default_tracking_source,
            ),
            default_reid_embedding_dim=_coerce_reid_embedding_dim(
                self._settings.value(self._KEYS["default_reid_embedding_dim"], defaults.default_reid_embedding_dim),
                defaults.default_reid_embedding_dim,
            ),
            default_min_iou=_coerce_float(
                self._settings.value(self._KEYS["default_min_iou"], defaults.default_min_iou),
                defaults.default_min_iou,
            ),
            default_min_tracker_confidence=_coerce_float(
                self._settings.value(
                    self._KEYS["default_min_tracker_confidence"], defaults.default_min_tracker_confidence
                ),
                defaults.default_min_tracker_confidence,
            ),
            default_confidence_decay=_coerce_float(
                self._settings.value(self._KEYS["default_confidence_decay"], defaults.default_confidence_decay),
                defaults.default_confidence_decay,
            ),
            default_offline_stitching_enabled=_coerce_bool(
                self._settings.value(
                    self._KEYS["default_offline_stitching_enabled"],
                    defaults.default_offline_stitching_enabled,
                ),
                defaults.default_offline_stitching_enabled,
            ),
            default_max_stitch_gap=_coerce_int(
                self._settings.value(self._KEYS["default_max_stitch_gap"], defaults.default_max_stitch_gap),
                defaults.default_max_stitch_gap,
            ),
            default_gsi_smoothness=_coerce_float(
                self._settings.value(self._KEYS["default_gsi_smoothness"], defaults.default_gsi_smoothness),
                defaults.default_gsi_smoothness,
            ),
            default_draw_boxes=_coerce_bool(
                self._settings.value(self._KEYS["default_draw_boxes"], defaults.default_draw_boxes),
                defaults.default_draw_boxes,
            ),
            default_box_border_width=_coerce_int(
                self._settings.value(
                    self._KEYS["default_box_border_width"], defaults.default_box_border_width
                ),
                defaults.default_box_border_width,
            ),
            default_show_preview_mask=_coerce_bool(
                self._settings.value(
                    self._KEYS["default_show_preview_mask"], defaults.default_show_preview_mask
                ),
                defaults.default_show_preview_mask,
            ),
            default_preview_blur_enabled=_coerce_bool(
                self._settings.value(
                    self._KEYS["default_preview_blur_enabled"], defaults.default_preview_blur_enabled
                ),
                defaults.default_preview_blur_enabled,
            ),
            default_blur_enabled=_coerce_bool(
                self._settings.value(self._KEYS["default_blur_enabled"], defaults.default_blur_enabled),
                defaults.default_blur_enabled,
            ),
            default_blur_strength=_coerce_float(
                self._settings.value(self._KEYS["default_blur_strength"], defaults.default_blur_strength),
                defaults.default_blur_strength,
            ),
            last_project_directory=_coerce_str(
                self._settings.value(self._KEYS["last_project_directory"], defaults.last_project_directory),
                defaults.last_project_directory,
            ),
            default_export_directory=_coerce_str(
                self._settings.value(self._KEYS["default_export_directory"], defaults.default_export_directory),
                defaults.default_export_directory,
            ),
            default_export_prefix=_coerce_str(
                self._settings.value(self._KEYS["default_export_prefix"], defaults.default_export_prefix),
                defaults.default_export_prefix,
            ),
            default_export_suffix=_coerce_str(
                self._settings.value(self._KEYS["default_export_suffix"], defaults.default_export_suffix),
                defaults.default_export_suffix,
            ),
        )

    def save(self, preferences: AppPreferences) -> None:
        """Persist all preferences and synchronize the backend.

        Args:
            preferences: Values to write under the store's stable preference keys.

        Returns:
            None.

        Raises:
            Exception: Propagates failures from the settings backend.

        Note:
            The label list is stored as a comma-separated string for compatibility.

        Example:
            store.save(AppPreferences(default_max_stitch_gap=25))
        """
        self._settings.setValue(self._KEYS["startup_fullscreen"], preferences.startup_fullscreen)
        self._settings.setValue(
            self._KEYS["default_detection_model_name"], preferences.default_detection_model_name
        )
        self._settings.setValue(
            self._KEYS["default_min_detection_confidence"], preferences.default_min_detection_confidence
        )
        self._settings.setValue(self._KEYS["default_chosen_labels"], preferences.chosen_labels_text)
        self._settings.setValue(self._KEYS["default_tracking_strategy"], preferences.default_tracking_strategy)
        self._settings.setValue(self._KEYS["default_tracking_source"], preferences.default_tracking_source)
        self._settings.setValue(self._KEYS["default_reid_embedding_dim"], preferences.default_reid_embedding_dim)
        self._settings.setValue(self._KEYS["default_min_iou"], preferences.default_min_iou)
        self._settings.setValue(
            self._KEYS["default_min_tracker_confidence"], preferences.default_min_tracker_confidence
        )
        self._settings.setValue(self._KEYS["default_confidence_decay"], preferences.default_confidence_decay)
        self._settings.setValue(
            self._KEYS["default_offline_stitching_enabled"], preferences.default_offline_stitching_enabled
        )
        self._settings.setValue(self._KEYS["default_max_stitch_gap"], preferences.default_max_stitch_gap)
        self._settings.setValue(self._KEYS["default_gsi_smoothness"], preferences.default_gsi_smoothness)
        self._settings.setValue(self._KEYS["default_draw_boxes"], preferences.default_draw_boxes)
        self._settings.setValue(
            self._KEYS["default_box_border_width"], preferences.default_box_border_width
        )
        self._settings.setValue(
            self._KEYS["default_show_preview_mask"], preferences.default_show_preview_mask
        )
        self._settings.setValue(
            self._KEYS["default_preview_blur_enabled"], preferences.default_preview_blur_enabled
        )
        self._settings.setValue(self._KEYS["default_blur_enabled"], preferences.default_blur_enabled)
        self._settings.setValue(self._KEYS["default_blur_strength"], preferences.default_blur_strength)
        self._settings.setValue(self._KEYS["last_project_directory"], preferences.last_project_directory)
        self._settings.setValue(self._KEYS["default_export_directory"], preferences.default_export_directory)
        self._settings.setValue(self._KEYS["default_export_prefix"], preferences.default_export_prefix)
        self._settings.setValue(self._KEYS["default_export_suffix"], preferences.default_export_suffix)
        self._settings.sync()
