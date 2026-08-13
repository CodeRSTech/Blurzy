"""Unit tests for detection model helper lists/view-model conversion."""

from __future__ import annotations

from app.infrastructure.detection.model.helpers import (
    DETECTION_MODEL_PROVIDER_ALL,
    DETECTION_MODEL_PROVIDER_MTCNN,
    DETECTION_MODEL_PROVIDER_TORCH,
    DETECTION_MODEL_PROVIDER_YOLO,
    get_detection_model_provider_options,
    get_available_detection_model_names_as_str,
    get_available_detection_model_names_as_view_model,
    resolve_detection_model_provider,
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

    def test_provider_options_match_expected_display_order(self):
        assert get_detection_model_provider_options() == [
            (DETECTION_MODEL_PROVIDER_ALL, "All Models"),
            (DETECTION_MODEL_PROVIDER_TORCH, "Torch models"),
            (DETECTION_MODEL_PROVIDER_YOLO, "YOLO models"),
            (DETECTION_MODEL_PROVIDER_MTCNN, "MTCNN models"),
        ]

    def test_provider_resolution_maps_each_model_family(self):
        assert resolve_detection_model_provider("None") == DETECTION_MODEL_PROVIDER_ALL
        assert resolve_detection_model_provider(next(iter(TORCH_MODELS))) == DETECTION_MODEL_PROVIDER_TORCH
        assert (
            resolve_detection_model_provider(next(iter(ULTRALYTICS_YOLO_MODELS)))
            == DETECTION_MODEL_PROVIDER_YOLO
        )
        assert resolve_detection_model_provider(MTCNN_MODELS[0]) == DETECTION_MODEL_PROVIDER_MTCNN

    def test_view_models_can_be_filtered_by_provider(self):
        torch_models = get_available_detection_model_names_as_view_model(DETECTION_MODEL_PROVIDER_TORCH)

        assert torch_models[0].model_id == "None"
        assert all(
            model.model_id == "None" or model.provider_id == DETECTION_MODEL_PROVIDER_TORCH
            for model in torch_models
        )
