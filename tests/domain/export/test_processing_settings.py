import pytest

from app.domain.detection.source import BoxSource
from app.domain.export.processing_settings import ProcessingSettings
from app.domain.tracking.tracking_strategy import TrackingStrategy


def test_botsort_strategy_and_box_source_values() -> None:
    assert TrackingStrategy.BOT_SORT.value == "botsort"
    assert BoxSource.TRACKING_BOTSORT.value == "Track (BoT-SORT)"


def test_reid_embedding_dimension_defaults_and_flows_to_view_model() -> None:
    settings = ProcessingSettings()

    assert settings.reid_embedding_dim == 256
    assert settings.as_view_model().reid_embedding_dim == 256


@pytest.mark.parametrize("dimension", [128, 256, 512])
def test_reid_embedding_dimension_accepts_supported_values(dimension: int) -> None:
    assert ProcessingSettings(reid_embedding_dim=dimension).reid_embedding_dim == dimension


def test_reid_embedding_dimension_rejects_unsupported_value() -> None:
    with pytest.raises(
        ValueError,
        match="^reid_embedding_dim must be one of 128, 256, or 512\\.$",
    ):
        ProcessingSettings(reid_embedding_dim=64)


def test_privacy_settings_defaults_and_view_model_mapping() -> None:
    settings = ProcessingSettings()
    view_model = settings.as_view_model()

    assert settings.privacy_features_enabled is False
    assert settings.resist_box_shrinking is True
    assert settings.shrink_resistance == 0.85
    assert settings.pre_detection_padding_sec == 0.5
    assert settings.post_detection_padding_sec == 0.5
    assert settings.box_safety_padding_pct == 0.10
    assert view_model.privacy_features_enabled is False
    assert view_model.resist_box_shrinking is True
    assert view_model.shrink_resistance == 0.85
    assert view_model.pre_detection_padding_sec == 0.5
    assert view_model.post_detection_padding_sec == 0.5
    assert view_model.box_safety_padding_pct == 0.10


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("shrink_resistance", -0.01, "shrink_resistance"),
        ("shrink_resistance", 1.0, "shrink_resistance"),
        ("pre_detection_padding_sec", -0.01, "pre_detection_padding_sec"),
        ("pre_detection_padding_sec", 5.01, "pre_detection_padding_sec"),
        ("post_detection_padding_sec", -0.01, "post_detection_padding_sec"),
        ("post_detection_padding_sec", 5.01, "post_detection_padding_sec"),
        ("box_safety_padding_pct", -0.01, "box_safety_padding_pct"),
        ("box_safety_padding_pct", 0.51, "box_safety_padding_pct"),
    ],
)
def test_privacy_settings_reject_out_of_range_values(
    field: str,
    value: float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        ProcessingSettings(**{field: value})
