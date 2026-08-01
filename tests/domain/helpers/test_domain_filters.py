"""Unit tests for ``new_passes_filter`` domain helper."""

from __future__ import annotations

from types import SimpleNamespace

from app.domain import ProcessingSettings, VideoDataLayer, new_passes_filter


def _make_settings() -> ProcessingSettings:
    return ProcessingSettings(
        min_detection_confidence=0.5,
        min_tracker_confidence=0.4,
        chosen_labels=["person"],
    )


def _box(*, label: str = "person", confidence: float = 0.9):
    # The helper only reads ``label`` and ``confidence``.
    return SimpleNamespace(label=label, confidence=confidence)


class TestNewPassesFilter:
    def test_layer_b_accepts_when_conf_and_label_pass(self):
        assert new_passes_filter(VideoDataLayer.B, _box(label="person", confidence=0.8), _make_settings()) is True

    def test_layer_b_rejects_when_conf_below_threshold(self):
        assert new_passes_filter(VideoDataLayer.B, _box(label="person", confidence=0.2), _make_settings()) is False

    def test_layer_b_rejects_when_label_not_selected(self):
        assert new_passes_filter(VideoDataLayer.B, _box(label="car", confidence=0.9), _make_settings()) is False

    def test_layer_d_rejects_when_tracker_conf_below_threshold(self):
        assert new_passes_filter(VideoDataLayer.D, _box(label="ignored", confidence=0.1), _make_settings()) is False

    def test_layer_a_does_not_apply_filtering_rules(self):
        assert new_passes_filter(VideoDataLayer.A, _box(label="car", confidence=0.01), _make_settings()) is True
