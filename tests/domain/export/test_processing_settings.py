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
