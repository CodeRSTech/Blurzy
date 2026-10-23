"""
Thread-safe CRUD store for bounding boxes with four-layer architecture support.

See Also:
    - [`SessionDataStoreInterface`][app.application.interfaces.session.session_data_store_interface.SessionDataStoreInterface] — describes the application-facing storage contract
    - [`VideoDataLayer`][app.domain.video.layer.VideoDataLayer] — identifies the stored annotation layers


Layer: Infrastructure.
Context: Implements concrete processing and I/O behind application-facing contracts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final
import threading
from collections import defaultdict

from PySide6.QtCore import QObject

from app.domain import VideoDataLayer, new_passes_filter
from app.shared import get_logger
from app.shared.box_io import box_to_dict, dict_to_box
if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Iterable
    from app.domain.base.dtypes import ListOfBoxes
    from app.domain.export.processing_settings import ProcessingSettings
    from app.domain.session.session_id import SessionId
    from app.domain.views.bounding_box_view_model import BBoxViewModel

logger = get_logger("Infrastructure->SessionDataStore")


@final
class SessionDataStore(QObject):
    """
    Attributes:
        _s_id (SessionId): Session ID that owns this store.
        _lock (threading.RLock): Reentrant lock protecting all store mutations.
        _data (dict[VideoDataLayer, dict[int, ListOfBoxes]]): Layer and frame indexed
            detection storage.

    ???+ abstract "Architecture"
        - Structure: `dict[DataLayer, dict[int, ListOfBoxes]]` for O(1)
          access.
        - Layers: A (raw detections), B (user-edited detections), C (raw tracks),
          and D (user-edited tracks).
        - Threading: protected by `threading.RLock()` for UI and worker access.

    ???+ info "Usage patterns"
        - Read: `get_boxes_for_layer_at_frame_index_as_list(A, 100)`.
        - Write: `add_boxes_to_layer_at_frame_index(B, 100, boxes)`.
        - Filter: `apply_filters_to_layer_b(settings)` preserves manual boxes while
          re-filtering AI boxes.
        - Clear: `clear_layer_by_name(B)` clears all boxes or preserves manual
          ones.
        - Copy: `overwrite_source_layer_to_target_layer(A, B)` deep-clones data.

    ???+ success "Thread safety"
        all methods use the RLock context manager, and manual boxes with
        `source = AnnotationBoxSource.MANUAL` are preserved across filters and selective clears.

    ???+ info "Design notes"
        - `defaultdict(list)` provides automatic empty frame allocation.
        - Box mutation occurs in place after the lock is acquired.


    Layer: Infrastructure.
    Context: Implements concrete processing or I/O behind application-facing contracts.


    Args:
        s_id: Identifier of the session associated with this object.
        parent: Optional Qt parent object.
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
        """
        Return reentrant lock protecting `_data` (used internally by all CRUD methods).

        Returns:
            The reentrant lock guarding the store's layer data.
        """
        logger.trace("Attempting to acquire data lock for session '{}'", self._s_id)
        return self._lock

    # ============================== READ ==============================

    def get_boxes_for_layer_at_frame_index_as_list(
            self, layer: VideoDataLayer, frame_index: int
    ) -> ListOfBoxes:
        """
        Retrieve all boxes for a given frame and layer in O(1) time.

        Args:
            layer: Layer whose frame data is requested.
            frame_index: Zero-based frame index to retrieve.

        Returns:
            The stored box list, or an empty list if the frame has no entry.

        Note:
            An existing list is returned directly, not cloned. Use store mutation
            methods when changing annotations so callers follow the locking contract.
        """
        with self.data_lock:
            return self._data[layer].get(frame_index, [])

    def get_all_boxes_for_layer_as_dict_of_lists(self, layer: VideoDataLayer) -> dict[int, ListOfBoxes]:
        """
        Return the store's frame-to-box mapping for a layer.

        Args:
            layer: Layer whose frame mapping is returned.

        Returns:
            The live mapping from frame indices to box lists; callers should use
            store methods rather than mutating this mapping directly.
        """
        with self.data_lock:
            return self._data[layer]

    def has_boxes_for_layer(self, layer: VideoDataLayer) -> bool:
        """
        Extremely fast boolean check if a layer contains any boxes across all frames.

        Args:
            layer: Layer to check.

        Returns:
            `True` if at least one frame in the layer contains a box.
        """
        with self.data_lock:
            return any(len(boxes) > 0 for boxes in self._data[layer].values())

    def has_boxes_for_layer_at_frame_index(self, layer: VideoDataLayer, frame_index: int) -> bool:
        """
        Extremely fast boolean check if any boxes exist for a frame.

        Args:
            layer: Layer to check.
            frame_index: Zero-based frame index to check.

        Returns:
            `True` if that frame contains one or more boxes.
        """
        with self.data_lock:
            return len(self._data[layer].get(frame_index, [])) > 0

    def has_frame_for_layer_at_frame_index(self, layer: VideoDataLayer, frame_index: int) -> bool:
        """
        Return whether a layer frame was initialized, even when it is intentionally empty.

        Args:
            layer: Layer to check.
            frame_index: Zero-based frame index to check.

        Returns:
            `True` if an entry exists for the frame, even when its box list is empty.
        """
        with self.data_lock:
            return frame_index in self._data[layer]

    # ============================== CREATE / UPDATE ==============================

    def add_box_to_layer_at_frame_index(
            self, layer: VideoDataLayer, frame_index: int, box: BBoxViewModel
    ) -> None:
        """
        Inserts a single bounding detection in true O(1) append time.

        Args:
            layer: Layer receiving the box.
            frame_index: Zero-based frame index to update.
            box: Box to append to that frame.
        """
        with self.data_lock:
            self._data[layer][frame_index].append(box)

    def add_boxes_to_layer_at_frame_index(
            self, layer: VideoDataLayer, frame_index: int, boxes: Iterable[BBoxViewModel]
    ) -> None:
        """
        Appends new boxes to the specified layer and frame natively.

        Args:
            layer: Layer receiving the boxes.
            frame_index: Zero-based frame index to update.
            boxes: Boxes to append to that frame.
        """
        if not boxes:
            return
        with self.data_lock:
            self._data[layer][frame_index].extend(boxes)

    def purge_boxes_in_layer_by_minimum_confidence_at_frame_index(
            self, layer: VideoDataLayer, min_conf: float, frame_index: int
    ) -> None:
        """
        Instantly deletes all AI boxes below a confidence threshold in a specific layer.

        Args:
            layer: Layer from which low-confidence machine boxes are removed.
            min_conf: Minimum confidence for retaining non-manual boxes with a score.
            frame_index: Zero-based frame index to filter.

        Note:
            Manual boxes and boxes without a confidence score are retained.
        """
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
        """
        Move boxes by (`delta_x`, `delta_y`) pixels, return count moved.

        Args:
            layer: Layer containing the boxes.
            frame_index: Zero-based frame index to edit.
            keys: Box keys identifying which boxes to move.
            delta_x: Horizontal translation in pixels.
            delta_y: Vertical translation in pixels.

        Returns:
            Number of matching boxes whose coordinates were updated.
        """
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
        """
        Move manual boxes only (`source = AnnotationBoxSource.MANUAL`) by delta, return count moved.

        Args:
            layer: Layer containing the boxes.
            frame_index: Zero-based frame index to edit.
            keys: Keys of manual boxes to move.
            delta_x: Horizontal translation in pixels.
            delta_y: Vertical translation in pixels.

        Returns:
            Number of matching manual boxes whose coordinates were updated.
        """
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
        """
        Delete all AI boxes below `min_conf` across all frames (preserves manual boxes).

        Args:
            layer: Layer from which low-confidence machine boxes are removed.
            min_conf: Minimum confidence for retaining non-manual boxes with a score.

        Note:
            Manual boxes and boxes without a confidence score are retained.
        """
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
        Re-filter source boxes into the target layer using the current session settings.

        Args:
            source_layer_name: Layer containing the unfiltered boxes to evaluate.
            target_layer_name: Editable layer receiving boxes that pass its filters.
            session_settings: Confidence and label settings used by `new_passes_filter`.

        Returns:
            Number of frames whose target-layer box count changed and was replaced.

        Note:
            Existing manual boxes in each target frame are cloned and retained.
            Machine boxes are cloned from the source layer before filtering. A
            target frame is replaced only when its resulting box count differs.
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
        """
        Wipes all tracking and detection layers.

        Args:
            keep_manual: Whether to retain manual boxes in editable layers B and D.
        """
        with self.data_lock:
            self.clear_layer_by_name(VideoDataLayer.A)
            self.clear_layer_by_name(VideoDataLayer.C)
            self.clear_layer_by_name(VideoDataLayer.B, keep_manual=keep_manual)
            self.clear_layer_by_name(VideoDataLayer.D, keep_manual=keep_manual)
            logger.info("Cleared all layers for session '{}'", self._s_id)

    def clear_layer_by_name(self, layer: VideoDataLayer, keep_manual: bool = False) -> None:
        """
        Clears boxes for a specific layer.

        Args:
            layer: Layer to clear.
            keep_manual: Whether to retain only manual boxes in the layer.
        """
        with self.data_lock:
            if not keep_manual:
                self._data[layer].clear()
            else:
                for frame_index, boxes in self._data[layer].items():
                    self._data[layer][frame_index] = [b for b in boxes if b.is_manual]

    def clear_layers_by_name(self, layers: list[VideoDataLayer]) -> None:
        """
        Clear layers by name.

        Args:
            layers: Layers whose contents should be cleared.
        """
        for layer in layers:
            self.clear_layer_by_name(layer)

    def delete_boxes_from_layer_by_id(self, layer: VideoDataLayer, box_ids: Iterable[str]) -> None:
        """
        Deletes specific boxes from a layer by their string keys/IDs.

        Args:
            layer: Layer from which matching boxes are removed.
            box_ids: Box keys (or IDs when a key is absent) to remove across frames.
        """
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
        """
        Instantly deletes specific boxes from a layer at a single frame index.

        Args:
            layer: Layer from which boxes are removed.
            box_ids: Box keys (or IDs when a key is absent) to remove.
            frame_index: Zero-based frame index to edit.

        Returns:
            `True` if at least one box was removed; otherwise `False`.
        """
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
        """
        Copy-and-overwrite a single frame's boxes from one layer to another.

Args:
    source_layer: Layer providing source boxes.
    target_layer: Layer whose box list at `index` will be replaced.
    index: Zero-based frame index.
"""
        with self.data_lock:
            source_boxes = self._data[source_layer].get(index, [])
            # Directly overwrite the target layer at this frame with fast-cloned boxes
            self._data[target_layer][index] = [box.clone() for box in source_boxes]
            logger.info("Reset Layer {} frame {} for session '{}'", target_layer, index, self._s_id)

    def overwrite_source_layer_to_target_layer(
            self, source_layer: VideoDataLayer, target_layer: VideoDataLayer,
            filter_fn: Callable[[BBoxViewModel], bool] | None = None
    ) -> None:
        """
        Copy all accepted boxes from a source layer to a target layer.

        Args:
            source_layer: Layer providing box data.
            target_layer: Layer replaced by the copy.
            filter_fn: Optional predicate that rejects source boxes.
        Raises:
            Exception: Propagates errors from the optional predicate.

        Note:
            Existing target data is cleared before cloned source boxes are written.

        Example:
            store.overwrite_source_layer_to_target_layer(VideoDataLayer.A, VideoDataLayer.B)
        """
        with self.data_lock:
            self.clear_layer_by_name(target_layer)
            for frame_index, boxes in self._data[source_layer].items():
                if boxes:
                    self._data[target_layer][frame_index] = [
                        box.clone()
                        for box in boxes
                        if filter_fn is None or filter_fn(box)
                    ]

    def overwrite_layer_with_dict_of_boxes(
            self, layer: VideoDataLayer, boxes_dict: dict[int, ListOfBoxes]
    ) -> None:
        """
        Replace a layer with lists keyed by zero-based frame index.

        Args:
            layer: Layer whose stored frame data is cleared and replaced.
            boxes_dict: Replacement box lists keyed by frame index.

        Note:
            Empty lists are omitted from storage. Each non-empty list is shallow
            copied; its box objects are not cloned.
        """
        with self.data_lock:
            self.clear_layer_by_name(layer)
            for frame_index, boxes in boxes_dict.items():
                if boxes:
                    self._data[layer][frame_index] = list(boxes)

    def overwrite_layer_at_index_with_boxes(
            self, layer: VideoDataLayer, frame_index: int, boxes: ListOfBoxes
    ) -> None:
        """
        Replace the stored box list for one layer and frame.

        Args:
            layer: Layer whose frame entry is replaced.
            frame_index: Zero-based frame index to update.
            boxes: New list assigned to that frame.

        Note:
            The supplied list and box objects are stored directly, not cloned.
        """
        with self.data_lock:
            self._data[layer][frame_index] = boxes

    def replace_machine_boxes_at_frame_index(
            self,
            layer: VideoDataLayer,
            frame_index: int,
            boxes: Iterable[BBoxViewModel],
            filter_fn: Callable[[BBoxViewModel], bool] | None = None,
    ) -> None:
        """
        Replace machine boxes in one frame while retaining manual annotations.

        Args:
            layer: Target layer whose machine boxes are refreshed.
            frame_index: Zero-based frame to replace.
            boxes: New machine-produced boxes for the frame.
            filter_fn: Optional predicate applied before new boxes are cloned.
        Raises:
            Exception: Propagates errors raised by `filter_fn`.

        Note:
            Manual boxes remain in their current order and retain their identity;
            each accepted machine box is cloned to keep layers independently editable.

        Example:
            store.replace_machine_boxes_at_frame_index(VideoDataLayer.B, 0, detections)
        """
        with self.data_lock:
            self._replace_machine_boxes_unlocked(layer, frame_index, boxes, filter_fn)

    def replace_machine_boxes_for_frames(
            self,
            layer: VideoDataLayer,
            boxes_by_frame: dict[int, ListOfBoxes],
            frame_count: int,
            filter_fn: Callable[[BBoxViewModel], bool] | None = None,
    ) -> None:
        """
        Refresh all machine boxes in a frame range under one lock acquisition.

        Args:
            layer: Target layer whose machine boxes are refreshed.
            boxes_by_frame: New machine boxes keyed by zero-based frame index.
            frame_count: Number of frames to refresh, covering `0..frame_count - 1`.
            filter_fn: Optional predicate applied before new boxes are cloned.
        Raises:
            ValueError: If `frame_count` is negative.
            Exception: Propagates errors raised by `filter_fn`.

        Note:
            Existing manual boxes are retained on every frame, including frames with
            no machine detections. Frames outside the requested range are unchanged.

        Example:
            store.replace_machine_boxes_for_frames(VideoDataLayer.D, tracked, frame_count)
        """
        if frame_count < 0:
            raise ValueError("frame_count must be non-negative.")

        with self.data_lock:
            for frame_index in range(frame_count):
                self._replace_machine_boxes_unlocked(
                    layer, frame_index, boxes_by_frame.get(frame_index, ()), filter_fn
                )

    def _replace_machine_boxes_unlocked(
            self,
            layer: VideoDataLayer,
            frame_index: int,
            boxes: Iterable[BBoxViewModel],
            filter_fn: Callable[[BBoxViewModel], bool] | None,
    ) -> None:
        """
        Replace a frame's machine boxes while the caller holds `data_lock`.

        Args:
            layer: Layer being updated.
            frame_index: Zero-based target frame.
            boxes: Candidate machine boxes.
            filter_fn: Optional acceptance predicate.
        Raises:
            Exception: Propagates filtering and cloning errors.

        Note:
            This helper deliberately does not acquire the lock so bulk updates can
            process every frame in one critical section.

        Example:
            store._replace_machine_boxes_unlocked(layer, 0, boxes, predicate)
        """
        current = self._data[layer].get(frame_index, [])
        manual_boxes = [box for box in current if box.is_manual]
        machine_boxes = [
            box.clone() for box in boxes
            if not box.is_manual and (filter_fn is None or filter_fn(box))
        ]
        self._data[layer][frame_index] = manual_boxes + machine_boxes

    def to_project_payload(self) -> dict[str, dict[str, list[dict[str, object]]]]:
        """
        Serialize session layer data into the project payload structure.

        Returns:
            Nested mapping of layer name to frame-index strings to serialized box dictionaries.
        """
        with self.data_lock:
            payload: dict[str, dict[str, list[dict[str, object]]]] = {}
            for layer, frames in self._data.items():
                payload[layer.value] = {
                    str(frame_index): [box_to_dict(box) for box in boxes]
                    for frame_index, boxes in frames.items()
                    if boxes
                }
            return payload

    def load_project_payload(self, payload: dict[str, dict[str, list[dict[str, object]]]]) -> None:
        """
        Replace stored layers with box data from a project payload.

        Args:
            payload: Mapping from layer names to frame-index strings and serialized box mappings.

        Raises:
            ValueError: If a layer name or frame-index string cannot be parsed.
            KeyError: If a serialized box is missing a required field.

        Note:
            All four layers are cleared before the payload is loaded.
        """
        with self.data_lock:
            for layer in VideoDataLayer:
                self._data[layer].clear()

            for layer_name, frames in payload.items():
                layer = VideoDataLayer(layer_name)
                for frame_index, boxes in frames.items():
                    self._data[layer][int(frame_index)] = [dict_to_box(box) for box in boxes]
