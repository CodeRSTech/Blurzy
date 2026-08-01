from unittest.mock import MagicMock

from app.infrastructure.detection import DetectionEngineAdapterFactory
from app.infrastructure.detection.model.names import TORCH_MODELS


def test_torch_model_registry_drives_engine_switching(monkeypatch):
    """Documented unit contract for torch-model iteration without heavyweight model loads.

    This replaces the old playground integration behaviour (real model boot + image IO)
    with a deterministic unit test that still validates the intended control flow:
      - first model -> factory.create(...)
      - subsequent models -> engine.set_model(...)
      - every model iteration calls detect(...)
    """

    # Keep the test focused: reduce the model registry to two entries.
    fake_models = {
        "Torch A": ("fake_model_a", "FakeWeightsA"),
        "Torch B": ("fake_model_b", "FakeWeightsB"),
    }
    monkeypatch.setattr("app.infrastructure.detection.model.names.TORCH_MODELS", fake_models)
    monkeypatch.setitem(globals(), "TORCH_MODELS", fake_models)

    frame = object()
    fake_engine = MagicMock()
    fake_engine.detect.return_value = [object()]

    fake_factory = MagicMock(spec=DetectionEngineAdapterFactory)
    fake_factory.create.return_value = fake_engine

    detection_engine = None
    for model_name in TORCH_MODELS:
        if detection_engine is not None:
            detection_engine.set_model(model_name)
        else:
            detection_engine = fake_factory.create(model_name=model_name)

        detections = detection_engine.detect(frame)
        assert detections is not None
        assert len(detections) > 0

    fake_factory.create.assert_called_once_with(model_name="Torch A")
    fake_engine.set_model.assert_called_once_with("Torch B")
    assert fake_engine.detect.call_count == 2

