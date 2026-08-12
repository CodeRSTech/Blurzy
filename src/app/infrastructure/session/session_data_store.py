"""Thread-safe CRUD store for bounding boxes with four-layer architecture support."""

from __future__ import annotations

from typing import TYPE_CHECKING


import threading
from collections import defaultdict

from typing import final, TYPE_CHECKING

from PySide6.QtCore import QObject

from app.domain import VideoDataLayer, new_passes_filter
from app.application.services.helpers.layer_io import _box_to_dict, _dict_to_box
from app.shared import get_logger
if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Iterable


if TYPE_CHECKING:
    from app.domain.base.dtypes import ListOfBoxes
    from app.domain.export.processing_settings import ProcessingSettings
    from app.domain.session.session_id import SessionId
    from app.domain.views.bounding_box_view_model import BBoxViewModel

logger = get_logger("Infrastructure->SessionDataStore")


@final
class SessionDataStore(QObject):
    """
    Thread-safe CRUD store for bounding boxes organized by layer and frame.

    Attributes:
        _s_id (SessionId): Session ID that owns this store.
        _lock (threading.RLock): Reentrant lock protecting all store mutations.
        _data (dict[VideoDataLayer, dict[int, ListOfBoxes]]): Layer and frame indexed
            detection storage.

    Note:
        Architecture:
            - Structure: ``dict[DataLayer, dict[int, ListOfBoxes]]`` for O(1)
              access.
            - Layers: A (raw detections), B (user-edited detections), C (raw tracks),
              and D (user-edited tracks).
            - Threading: protected by ``threading.RLock()`` for UI and worker access.

        Usage patterns:
            - Read: ``get_boxes_for_layer_at_frame_index_as_list(A, 100)``.
            - Write: ``add_boxes_to_layer_at_frame_index(B, 100, boxes)``.
            - Filter: ``apply_filters_to_layer_b(settings)`` preserves manual boxes while
              re-filtering AI boxes.
            - Clear: ``clear_layer_by_name(B)`` clears all boxes or preserves manual
              ones.
            - Copy: ``overwrite_source_layer_to_target_layer(A, B)`` deep-clones data.

        Thread safety: all methods use the RLock context manager, and manual boxes with
        ``source = AnnotationBoxSource.MANUAL`` are preserved across filters and selective clears.

        Design notes:
            - ``defaultdict(list)`` provides automatic empty frame allocation.
            - Box mutation occurs in place after the lock is acquired.
    """

    def __init__(self, s_id: SessionId, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._s_id = s_id
        self._lock = threading.RLock()

        # O(1) Memory Layout: Layer -> Frame Index -> List of Boxes
        self._data: dict[VideoDataLayer, dict[int, ListOfBoxes]] = {
            VideoDataLayer.A: defaultdict(list),
            VideoDataLayer.B: defaultdict(list),
            VideoDataLayer.C: defaultdict(list),
            VideoDataLayer.D: defaultdict(list),
        }

    def __repr__(self):
        return f"<{self.__class__.__name__} session_id={self._s_id}>"

    @property
    def data_lock(self) -> threading.RLock:
        """Return reentrant lock protecting ``_data`` (used internally by all CRUD methods)."""
        logger.trace("Attempting to acquire data lock for session '{}'", self._s_id)
        return self._lock

    # ============================== READ ==============================

    def get_boxes_for_layer_at_frame_index_as_list(
            self, layer: VideoDataLayer, frame_index: int
    ) -> ListOfBoxes:
        """Retrieve all boxes for a given frame and layer in O(1) time."""
        with self.data_lock:
            return self._data[layer].get(frame_index, [])

    def get_all_boxes_for_layer_as_dict_of_lists(self, layer: VideoDataLayer) -> dict[int, ListOfBoxes]:
        """Returns a snapshot of the layer for legacy compatibility."""
        with self.data_lock:
            return self._data[layer]

    def has_boxes_for_layer(self, layer: VideoDataLayer) -> bool:
        """Extremely fast boolean check if a layer contains any boxes across all frames."""
        with self.data_lock:
            return any(len(boxes) > 0 for boxes in self._data[layer].values())

    def has_boxes_for_layer_at_frame_index(self, layer: VideoDataLayer, frame_index: int) -> bool:
        """Extremely fast boolean check if any boxes exist for a frame."""
        with self.data_lock:
            return len(self._data[layer].get(frame_index, [])) > 0

    def has_frame_for_layer_at_frame_index(self, layer: VideoDataLayer, frame_index: int) -> bool:
        """Return whether a layer frame was initialized, even when it is intentionally empty."""
        with self.data_lock:
            return frame_index in self._data[layer]

    # ============================== CREATE / UPDATE ==============================

    def add_box_to_layer_at_frame_index(
            self, layer: VideoDataLayer, frame_index: int, box: BBoxViewModel
    ) -> None:
        """Inserts a single bounding detection in true O(1) append time."""
        with self.data_lock:
            self._data[layer][frame_index].append(box)

    def add_boxes_to_layer_at_frame_index(
            self, layer: VideoDataLayer, frame_index: int, boxes: Iterable[BBoxViewModel]
    ) -> None:
        """Appends new boxes to the specified layer and frame natively."""
        if not boxes:
            return
        with self.data_lock:
            self._data[layer][frame_index].extend(boxes)

    def purge_boxes_in_layer_by_minimum_confidence_at_frame_index(
            self, layer: VideoDataLayer, min_conf: float, frame_index: int
    ) -> None:
        """Instantly deletes all AI boxes below a confidence threshold in a specific layer."""
        with self.data_lock:
            self._data[layer][frame_index] = [
                b
                for b in self._data[layer][frame_index]
                if b.is_manual or getattr(b, "confidence",
                                                                           None) is None or b.confidence >= min_conf
            ]

    def move_boxes_in_layer_at_frame_index_by_delta(
            self, layer: VideoDataLayer, frame_index: int, keys: set[str], delta_x: float, delta_y: float
    ) -> int:
        """Move boxes by (``delta_x``, ``delta_y``) pixels, return count moved."""
        moved = 0
        with self.data_lock:
            boxes = self._data[layer][frame_index]
            for item in boxes:
                if item.key not in keys:
                    continue
                x1, y1, x2, y2 = item.bbox_xyxy
                item.bbox_xyxy = (
                    int(x1 + delta_x),
                    int(y1 + delta_y),
                    int(x2 + delta_x),
                    int(y2 + delta_y),
                )
                moved += 1
        return moved

    def move_manual_boxes_in_layer_at_frame_index_by_delta(
            self, layer: VideoDataLayer, frame_index: int, keys: set[str], delta_x: float, delta_y: float
    ) -> int:
        """Move manual boxes only (``source = AnnotationBoxSource.MANUAL``) by delta, return count moved."""
        moved = 0
        with self.data_lock:
            boxes = self._data[layer][frame_index]
            for item in boxes:
                if item.key not in keys or not item.is_manual:
                    continue
                x1, y1, x2, y2 = item.bbox_xyxy
                item.bbox_xyxy = (
                    int(x1 + delta_x),
                    int(y1 + delta_y),
                    int(x2 + delta_x),
                    int(y2 + delta_y),
                )
                moved += 1
        return moved

    # ============================== DELETE ==============================

    def purge_boxes_in_layer_by_minimum_confidence(self, layer: VideoDataLayer, min_conf: float) -> None:
        """Delete all AI boxes below ``min_conf`` across all frames (preserves manual boxes)."""
        with self.data_lock:
            for frame_index, boxes in self._data[layer].items():
                self._data[layer][frame_index] = [
                    b
                    for b in boxes
                    if b.is_manual
                       or getattr(b, "confidence", None) is None
                       or b.confidence >= min_conf
                ]

    def apply_filters_to_layers(self, source_layer_name: VideoDataLayer, target_layer_name: VideoDataLayer,
                                session_settings: ProcessingSettings) -> int:
        """
        Apply filtering logic to bounding boxes in the source layer to populate the target layer for the session.
        """

        changed_frames = 0

        with self.data_lock:
            # We must iterate over the source layer so we can "bring back" boxes if the threshold is lowered
            for frame_idx, source_layer_boxes in self._data[source_layer_name].items():
                target_layer_boxes = self._data[target_layer_name][frame_idx]

                # Preserve any manual annotations the user added
                # [NOTE] [EXPERIMENTAL] This is a temporary solution to preserve manual boxes that needs to be tested
                manual_boxes = [i.clone() for i in target_layer_boxes if i.is_manual]

                # Re-filter the pristine detections from the source layer
                filtered_detections = [i.clone() for i in source_layer_boxes if
                                       new_passes_filter(target_layer_name, i, session_settings)]

                # Combine them
                new_target_layer_boxes = manual_boxes + filtered_detections

                if len(new_target_layer_boxes) != len(target_layer_boxes):
                    self._data[target_layer_name][frame_idx] = new_target_layer_boxes
                    changed_frames += 1

        return changed_frames

    def clear_all_layers(self, keep_manual: bool = False) -> None:
        """Wipes all tracking and detection layers."""
        with self.data_lock:
            self.clear_layer_by_name(VideoDataLayer.A)
            self.clear_layer_by_name(VideoDataLayer.C)
            self.clear_layer_by_name(VideoDataLayer.B, keep_manual=keep_manual)
            self.clear_layer_by_name(VideoDataLayer.D, keep_manual=keep_manual)
            logger.info("Cleared all layers for session '{}'", self._s_id)

    def clear_layer_by_name(self, layer: VideoDataLayer, keep_manual: bool = False) -> None:
        """Clears boxes for a specific layer."""
        with self.data_lock:
            if not keep_manual:
                self._data[layer].clear()
            else:
                for frame_index, boxes in self._data[layer].items():
                    self._data[layer][frame_index] = [b for b in boxes if b.is_manual]

    def clear_layers_by_name(self, layers: list[VideoDataLayer]) -> None:
        for layer in layers:
            self.clear_layer_by_name(layer)

    def delete_boxes_from_layer_by_id(self, layer: VideoDataLayer, box_ids: Iterable[str]) -> None:
        """Deletes specific boxes from a layer by their string keys/IDs."""
        with self.data_lock:
            ids_to_drop = set(box_ids)
            if not ids_to_drop:
                return

            for frame_index, boxes in self._data[layer].items():
                self._data[layer][frame_index] = [
                    b for b in boxes if getattr(b, "key", getattr(b, "id", "")) not in ids_to_drop
                ]

    def delete_boxes_from_layer_by_id_at_frame_index(
            self, layer: VideoDataLayer, box_ids: Iterable[str], frame_index: int
    ) -> bool:
        """Instantly deletes specific boxes from a layer at a single frame index."""
        with self.data_lock:
            ids_to_drop = set(box_ids)
            if not ids_to_drop:
                return False

            boxes = self._data[layer].get(frame_index, [])
            if not boxes:
                return False

            original_len = len(boxes)
            new_boxes = [b for b in boxes if getattr(b, "key", getattr(b, "id", "")) not in ids_to_drop]

            if len(new_boxes) != original_len:
                self._data[layer][frame_index] = new_boxes
                logger.info(
                    "Deleted {} item(s) from session '{}' frame {}",
                    original_len - len(new_boxes),
                    self._s_id,
                    frame_index,
                )
                return True
            return False

    def overwrite_source_to_target_layer_at_index(
            self, source_layer: VideoDataLayer, target_layer: VideoDataLayer, index: int
    ) -> None:
        """Copy-and-overwrite a single frame's boxes from one layer to another."""
        with self.data_lock:
            source_boxes = self._data[source_layer].get(index, [])
            # Directly overwrite the target layer at this frame with fast-cloned boxes
            self._data[target_layer][index] = [box.clone() for box in source_boxes]
            logger.info("Reset Layer {} frame {} for session '{}'", target_layer, index, self._s_id)

    def overwrite_source_layer_to_target_layer(
            self, source_layer: VideoDataLayer, target_layer: VideoDataLayer,
            filter_fn: Callable[[BBoxViewModel], bool] | None = None
    ) -> None:
        """Copy-and-overwrite an entire layer using fast object cloning."""
        if filter_fn is None:
            filter_fn = lambda _: True
        with self.data_lock:
            self.clear_layer_by_name(target_layer)
            for frame_index, boxes in self._data[source_layer].items():
                if boxes and filter_fn is not None:
                    self._data[target_layer][frame_index] = [box.clone() for box in boxes if filter_fn(box)]

    def overwrite_layer_with_dict_of_boxes(
            self, layer: VideoDataLayer, boxes_dict: dict[int, ListOfBoxes]
    ) -> None:
        """Replaces the entire layer with a new dictionary of boxes."""
        with self.data_lock:
            self.clear_layer_by_name(layer)
            for frame_index, boxes in boxes_dict.items():
                if boxes:
                    self._data[layer][frame_index] = list(boxes)

    def overwrite_layer_at_index_with_boxes(
            self, layer: VideoDataLayer, frame_index: int, boxes: ListOfBoxes
    ) -> None:
        """Replaces the entire layer with a new dictionary of boxes."""
        with self.data_lock:
            self._data[layer][frame_index] = boxes

    def to_project_payload(self) -> dict[str, dict[str, list[dict[str, object]]]]:
        with self.data_lock:
            payload: dict[str, dict[str, list[dict[str, object]]]] = {}
            for layer, frames in self._data.items():
                payload[layer.value] = {
                    str(frame_index): [_box_to_dict(box) for box in boxes]
                    for frame_index, boxes in frames.items()
                    if boxes
                }
            return payload

    def load_project_payload(self, payload: dict[str, dict[str, list[dict[str, object]]]]) -> None:
        with self.data_lock:
            for layer in VideoDataLayer:
                self._data[layer].clear()

            for layer_name, frames in payload.items():
                layer = VideoDataLayer(layer_name)
                for frame_index, boxes in frames.items():
                    self._data[layer][int(frame_index)] = [_dict_to_box(box) for box in boxes]
