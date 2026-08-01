"""Unit tests for detection model helper lists/view-model conversion."""

from __future__ import annotations

from app.infrastructure.detection.model.helpers import (
    get_available_detection_model_names_as_str,
    get_available_detection_model_names_as_view_model,
)
from app.infrastructure.detection.model.names import MTCNN_MODELS, TORCH_MODELS, ULTRALYTICS_YOLO_MODELS


class TestDetectionModelHelpers:
    def test_string_list_starts_with_none_and_includes_all_registered_names(self):
        names = get_available_detection_model_names_as_str()

        assert names[0] == "None"
        assert all(name in names for name in TORCH_MODELS.keys())
        assert all(name in names for name in ULTRALYTICS_YOLO_MODELS.keys())
        assert all(name in names for name in MTCNN_MODELS)

    def test_string_list_has_expected_size(self):
        names = get_available_detection_model_names_as_str()
        expected = 1 + len(TORCH_MODELS) + len(ULTRALYTICS_YOLO_MODELS) + len(MTCNN_MODELS)
        assert len(names) == expected

    def test_view_models_map_model_id_and_display_name_from_names(self):
        names = get_available_detection_model_names_as_str()
        models = get_available_detection_model_names_as_view_model()

        assert len(models) == len(names)
        assert [m.model_id for m in models] == names
        assert [m.display_name for m in models] == names
