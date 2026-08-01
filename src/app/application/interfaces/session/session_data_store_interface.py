"""Data-only interface contract for ``SessionDataStore`` CRUD operations."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Protocol

from app.domain  import VideoDataLayer,ListOfBoxes, ProcessingSettings, BBoxViewModel


class SessionDataStoreInterface(Protocol):
    """Data operations contract for session detection storage and mutation."""

    # ============================== READ ==============================

    def get_boxes_for_layer_at_frame_index_as_list(
        self, layer: VideoDataLayer, frame_index: int
    ) -> ListOfBoxes:
        ...

    def get_all_boxes_for_layer_as_dict_of_lists(self, layer: VideoDataLayer) -> dict[int, ListOfBoxes]:
        ...

    def has_boxes_for_layer(self, layer: VideoDataLayer) -> bool:
        ...

    def has_boxes_for_layer_at_frame_index(self, layer: VideoDataLayer, frame_index: int) -> bool:
        ...

    # ============================== CREATE / UPDATE ==============================

    def add_box_to_layer_at_frame_index(
        self, layer: VideoDataLayer, frame_index: int, box: BBoxViewModel
    ) -> None:
        ...

    def add_boxes_to_layer_at_frame_index(
        self, layer: VideoDataLayer, frame_index: int, boxes: Iterable[BBoxViewModel]
    ) -> None:
        ...

    def purge_boxes_in_layer_by_minimum_confidence_at_frame_index(
        self, layer: VideoDataLayer, min_conf: float, frame_index: int
    ) -> None:
        ...

    def move_boxes_in_layer_at_frame_index_by_delta(
        self, layer: VideoDataLayer, frame_index: int, keys: set[str], delta_x: float, delta_y: float
    ) -> int:
        ...

    def move_manual_boxes_in_layer_at_frame_index_by_delta(
        self, layer: VideoDataLayer, frame_index: int, keys: set[str], delta_x: float, delta_y: float
    ) -> int:
        ...

    # ============================== DELETE ==============================

    def purge_boxes_in_layer_by_minimum_confidence(self, layer: VideoDataLayer, min_conf: float) -> None:
        ...

    def apply_filters_to_layers(
        self, source_layer_name: VideoDataLayer, target_layer_name: VideoDataLayer, session_settings: ProcessingSettings
    ) -> int:
        ...

    def clear_all_layers(self, keep_manual: bool = False) -> None:
        ...

    def clear_layer_by_name(self, layer: VideoDataLayer, keep_manual: bool = False) -> None:
        ...

    def clear_layers_by_name(self, layers: list[VideoDataLayer]) -> None:
        ...

    def delete_boxes_from_layer_by_id(self, layer: VideoDataLayer, box_ids: Iterable[str]) -> None:
        ...

    def delete_boxes_from_layer_by_id_at_frame_index(
        self, layer: VideoDataLayer, box_ids: Iterable[str], frame_index: int
    ) -> bool:
        ...

    def overwrite_source_to_target_layer_at_index(
        self, source_layer: VideoDataLayer, target_layer: VideoDataLayer, index: int
    ) -> None:
        ...

    def overwrite_source_layer_to_target_layer(
        self,
        source_layer: VideoDataLayer,
        target_layer: VideoDataLayer,
        filter_fn: Callable[[BBoxViewModel], bool] | None = None,
    ) -> None:
        ...

    def overwrite_layer_with_dict_of_boxes(
        self, layer: VideoDataLayer, boxes_dict: dict[int, ListOfBoxes]
    ) -> None:
        ...

    def overwrite_layer_at_index_with_boxes(
        self, layer: VideoDataLayer, frame_index: int, boxes: ListOfBoxes
    ) -> None:
        ...
