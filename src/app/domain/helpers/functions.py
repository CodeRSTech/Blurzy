"""Domain utility functions for string handling and validation."""
from __future__ import annotations

from collections.abc import Iterable

from app.domain import VideoDataLayer, BBoxViewModel, ProcessingSettings
from app.domain.base.dtypes import ListOfBoxes
from app.domain.base.exceptions import EmptySetGeneratedFromKeysError
from app.domain.detection.result import DetectionResult


def str_iterable_as_set_without_null_values(iterable: Iterable[str]) -> set[str]:
    """
    Convert string iterable to set, filtering falsy values.

    Args:
        iterable (Iterable[str]): Input values to clean and deduplicate.

    Returns:
        set[str]: A set containing only truthy string values from ``iterable``.

    Raises:
        EmptySetGeneratedFromKeysError: If every item in ``iterable`` is falsy.

    Note:
        Filters out empty or otherwise falsy values, deduplicates the remaining
        strings by converting them to a set, and validates that at least one
        usable value remains.

    Example:
        keys = ["person", "car", "", None, "person"]  # With empties
        result = str_iterable_as_set_without_null_values(keys)
        # → {"person", "car"}  (deduplicated, cleaned)

        empty_keys = ["", "", ""]
        result = str_iterable_as_set_without_null_values(empty_keys)
        # → EmptySetGeneratedFromKeysError (all were falsy)
    """
    set_to_return = {k for k in iterable if k}
    if not set_to_return:
        raise EmptySetGeneratedFromKeysError("Empty set was generated from keys.")
    return set_to_return


def map_detections_to_bbox(
        detections: list[DetectionResult],
) -> ListOfBoxes:
    """
    Maps a list of ``DetectionResult`` objects to a list of ``BBoxViewModel`` objects for UI display.

    Note:
        ``DetectionResult`` ≡ ``BBoxViewModel`` But,

        ``BBoxViewModel`` is used for UI representation and,
        includes literal attributes ``source`` and ``key``.

    Args:
        detections: List of ``DetectionResult`` objects to be mapped.

    Returns:
        List of ``BBoxViewModel`` objects representing the mapped detections.
    """
    return [d.to_frame_box_view_model() for d in detections]


def new_passes_filter(layer_name: VideoDataLayer, box: BBoxViewModel, settings: ProcessingSettings) -> bool:
    """
    Determines if a detection item passes the filter criteria for Layer B/D based on confidence and label settings.

    Filter Criteria:
        - Confidence: The detection's confidence must be greater than or equal to the minimum detection confidence.
        - Label: If specific labels are chosen, the detection's label must be in the chosen labels list.

    Args:
        layer_name (VideoDataLayer): The layer name for which the filter is applied.
        box (BBoxViewModel): The detection item to be evaluated.
        settings (ProcessingSettings): The processing settings containing filter criteria.

    Returns:
        bool: True if the detection passes the filter, False otherwise.
    """

    conf = box.confidence

    if layer_name == VideoDataLayer.B:
        conf_threshold = settings.min_detection_confidence
        labels_choice = settings.chosen_labels

        if (conf and conf < conf_threshold) or (labels_choice and box.label not in labels_choice):
            return False

    if layer_name == VideoDataLayer.D:
        conf_threshold = settings.min_tracker_confidence
        if conf and conf < conf_threshold:
            return False

    return True
