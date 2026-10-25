"""
Session-owned annotation storage indexed by layer and frame.

Implements the
[`SessionDataStoreInterface`][app.application.interfaces.session.session_data_store_interface.SessionDataStoreInterface]
contract for the four
[`VideoDataLayer`][app.domain.video.layer.VideoDataLayer]
values. Store operations use a reentrant lock, but read methods can expose live
mutable objects; callers must respect the ownership and locking rules below.

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
    Store a session's detection and tracking boxes by layer and frame index.

    ???+ abstract "Architecture"

        - Structure: `dict[VideoDataLayer, dict[int, ListOfBoxes]]`.
        - Layers: A (raw detections), B (user-edited detections), C (raw tracks),
          and D (user-edited tracks).
        - Missing frames and initialized frames with no boxes are distinct states.
        - Layer roles are workflow conventions, not access restrictions enforced
          by this store; mutation methods accept any layer.

    !!! warning "Live data is not a thread-safe snapshot"

        Getters release the lock before returning lists or mappings owned by the
        store. Coordinate subsequent access with `data_lock` or use store methods
        to mutate annotations. Replacement operations can detach previously
        returned lists. Box objects may also be shared with callers, depending on
        the write method. A lock does not provide rollback on failure.

    Frame indices are conventionally zero-based; this store does not generally
    validate bounds against a video. Manual-box preservation is method-specific,
    not a guarantee of every clear, overwrite, or delete operation.

    Examples:
        Given an initialized `store` and an iterable of `detections`:

        ```python
        from app.domain.video.layer import VideoDataLayer

        store.add_boxes_to_layer_at_frame_index(VideoDataLayer.A, 0, detections)
        store.overwrite_source_layer_to_target_layer(VideoDataLayer.A, VideoDataLayer.B)
        with store.data_lock:
            count = len(store.get_boxes_for_layer_at_frame_index_as_list(VideoDataLayer.B, 0))
        ```
    """

    def __init__(self, s_id: SessionId, parent: QObject | None = None) -> None:
        """Create empty storage for all four annotation layers.

        Args:
            s_id: Identifier of the session owning this store.
            parent: Optional Qt parent controlling QObject ownership.
        """
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
        Return the lock used to coordinate access to stored annotation data.

        Returns:
            The existing reentrant lock, not an acquired lock or a new instance.

        Use it as a context manager when accessing live data across multiple
        calls. Acquiring it does not protect against callers that bypass the
        locking contract.
        """
        logger.trace("Attempting to acquire data lock for session '{}'", self._s_id)
        return self._lock

    # ============================== READ ==============================

    def get_boxes_for_layer_at_frame_index_as_list(
            self, layer: VideoDataLayer, frame_index: int
    ) -> ListOfBoxes:
        """
        Retrieve the stored box list for a frame without cloning it.

        Args:
            layer: Layer whose frame data is requested.
            frame_index: Zero-based frame index to retrieve.

        Returns:
            The live stored list, or a new empty list if the frame has no entry.
            Reading an absent frame does not initialize its entry.

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

        !!! warning "Lock lifetime"

            The method releases its lock before returning. Hold `data_lock`
            around subsequent iteration when concurrent store writes are possible.
            Indexing a missing key in this `defaultdict` creates an empty entry.
        """
        with self.data_lock:
            return self._data[layer]

    def has_boxes_for_layer(self, layer: VideoDataLayer) -> bool:
        """
        Check whether any frame in a layer contains boxes.

        Args:
            layer: Layer to check.

        Returns:
            `True` if at least one frame in the layer contains a box.
        """
        with self.data_lock:
            return any(len(boxes) > 0 for boxes in self._data[layer].values())

    def has_boxes_for_layer_at_frame_index(self, layer: VideoDataLayer, frame_index: int) -> bool:
        """
        Check whether a frame contains at least one box.

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

        Unlike the box-presence checks, this distinguishes an initialized empty
        frame from one that has never been stored.
        """
        with self.data_lock:
            return frame_index in self._data[layer]

    # ============================== CREATE / UPDATE ==============================

    def add_box_to_layer_at_frame_index(
            self, layer: VideoDataLayer, frame_index: int, box: BBoxViewModel
    ) -> None:
        """
        Append one box to a frame, initializing its entry when absent.

        Args:
            layer: Layer receiving the box.
            frame_index: Zero-based frame index to update.
            box: Box to append to that frame.

        The box is stored by reference; later in-place changes affect callers
        sharing that object.
        """
        with self.data_lock:
            self._data[layer][frame_index].append(box)

    def add_boxes_to_layer_at_frame_index(
            self, layer: VideoDataLayer, frame_index: int, boxes: Iterable[BBoxViewModel]
    ) -> None:
        """
        Append boxes to a frame without cloning their objects.

        Args:
            layer: Layer receiving the boxes.
            frame_index: Zero-based frame index to update.
            boxes: Boxes to append to that frame.

        Falsy containers are ignored without initializing a frame. Other
        iterables are consumed under the lock; an empty iterator can initialize
        an empty entry, and an iterator error can leave a partially extended list.
        """
        if not boxes:
            return
        with self.data_lock:
            self._data[layer][frame_index].extend(boxes)

    def purge_boxes_in_layer_by_minimum_confidence_at_frame_index(
            self, layer: VideoDataLayer, min_conf: float, frame_index: int
    ) -> None:
        """
        Remove scored, non-manual boxes below a frame's confidence threshold.

        Args:
            layer: Layer from which low-confidence machine boxes are removed.
            min_conf: Minimum confidence for retaining non-manual boxes with a score.
            frame_index: Zero-based frame index to filter.

        Note:
            Manual boxes and boxes without a confidence score are retained.
            The stored list is replaced, but retained box objects are not cloned.
            An absent frame is initialized with an empty list.
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

        Updates shared box objects in place, converting each translated
        coordinate with `int()` and without clipping to video bounds. Looking up
        an absent frame initializes an empty entry.
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
        Move only matching boxes whose `is_manual` property is true.

        Args:
            layer: Layer containing the boxes.
            frame_index: Zero-based frame index to edit.
            keys: Keys of manual boxes to move.
            delta_x: Horizontal translation in pixels.
            delta_y: Vertical translation in pixels.

        Returns:
            Number of matching manual boxes whose coordinates were updated.

        Coordinates are updated in place using `int()` after translation, without
        clipping to video bounds. An absent frame is initialized as empty.
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
        Remove scored, non-manual boxes below `min_conf` across stored frames.

        Args:
            layer: Layer from which low-confidence machine boxes are removed.
            min_conf: Minimum confidence for retaining non-manual boxes with a score.

        Note:
            Manual boxes and boxes without a confidence score are retained.
            Each frame list is replaced while retained box objects keep their
            identity. No new frame indices are introduced.
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
            Source boxes that pass `new_passes_filter` are cloned, then combined
            with the retained manual clones. Only source frame indices are
            visited; missing target entries are initialized as empty.

        !!! warning "Count-based replacement"

            A target list is replaced only when its resulting box count differs.
            Equal-count changes to identity, coordinates, or content are not
            applied. Source and target should be distinct layers. Filter or clone
            failures propagate and may leave earlier frames updated.
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
        Clear all layers while holding the lock across the operation.

        Args:
            keep_manual: Whether to retain manual boxes in editable layers B and D.

        Layers A and C are always fully cleared. When preserving manual boxes,
        B/D frame entries remain present, even if their lists become empty.
        """
        with self.data_lock:
            self.clear_layer_by_name(VideoDataLayer.A)
            self.clear_layer_by_name(VideoDataLayer.C)
            self.clear_layer_by_name(VideoDataLayer.B, keep_manual=keep_manual)
            self.clear_layer_by_name(VideoDataLayer.D, keep_manual=keep_manual)
            logger.info("Cleared all layers for session '{}'", self._s_id)

    def clear_layer_by_name(self, layer: VideoDataLayer, keep_manual: bool = False) -> None:
        """
        Clear a layer, optionally retaining its manual boxes.

        Args:
            layer: Layer to clear.
            keep_manual: Whether to retain only manual boxes in the layer.

        With `keep_manual=False`, frame entries are removed. Otherwise existing
        entries remain, their lists are replaced, and retained boxes are not
        cloned. This method does not restrict manual preservation to B/D.
        """
        with self.data_lock:
            if not keep_manual:
                self._data[layer].clear()
            else:
                for frame_index, boxes in self._data[layer].items():
                    self._data[layer][frame_index] = [b for b in boxes if b.is_manual]

    def clear_layers_by_name(self, layers: list[VideoDataLayer]) -> None:
        """
        Clear each requested layer using separate lock acquisitions.

        Args:
            layers: Layers whose contents should be cleared.

        The sequence is not atomic across layers. Callers needing a single
        critical section can hold `data_lock` around the call.
        """
        for layer in layers:
            self.clear_layer_by_name(layer)

    def delete_boxes_from_layer_by_id(self, layer: VideoDataLayer, box_ids: Iterable[str]) -> None:
        """
        Delete boxes whose key matches a requested identifier across frames.

        Args:
            layer: Layer from which matching boxes are removed.
            box_ids: Box keys (or IDs when a key is absent) to remove across frames.

        The iterable is consumed once into a set. An empty set does nothing.
        An existing empty `key` does not fall back to `id`. Frame entries remain
        initialized; retained box objects are not cloned.
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
        Delete boxes with matching keys from one existing frame.

        Args:
            layer: Layer from which boxes are removed.
            box_ids: Box keys (or IDs when a key is absent) to remove.
            frame_index: Zero-based frame index to edit.

        Returns:
            `True` if at least one box was removed; otherwise `False`.

        An absent frame is not initialized. An existing empty `key` does not fall
        back to `id`. When boxes are removed, the frame list is replaced without
        cloning retained objects.
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

        Boxes are cloned before replacing the target list. An absent or empty
        source produces an initialized empty target entry. Passing the same
        layer clones that frame in place; cloning errors leave its old list intact.
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
            filter_fn: Acceptance predicate; `True` includes a box. `None`
                accepts all source boxes. Runs under the store lock.

        !!! warning "Destructive replacement"

            Use distinct source and target layers: the target is cleared first,
            so copying a layer onto itself clears its source too. Predicate or
            cloning errors propagate and may leave the target partially written.

        Only non-empty source frames are visited. Accepted boxes are cloned;
        a predicate rejecting every box still produces an empty target entry
        for that non-empty source frame.

        Examples:
            Given an initialized `store`:

            ```python
            store.overwrite_source_layer_to_target_layer(VideoDataLayer.A, VideoDataLayer.B)
            ```

            Import `VideoDataLayer` from `app.domain.video.layer`.
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

        Supply a mapping independent of this layer's live mapping: the layer
        is cleared before input iteration. Failures during iteration/copying
        propagate without restoring the previous contents.
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
            filter_fn: Acceptance predicate for non-manual candidates; `True`
                includes a box and `None` accepts all. Runs under the store lock.

        Note:
            Manual boxes remain in their current order and retain their identity;
            each accepted machine box is cloned to keep layers independently editable.
            Manual candidates in `boxes` are ignored. An empty result still
            initializes the frame. Iteration, predicate, and cloning errors
            propagate before the replacement list is assigned.

        Examples:
            Given `store`, candidate `detections`, and `VideoDataLayer` imported
            from `app.domain.video.layer`:

            ```python
            store.replace_machine_boxes_at_frame_index(VideoDataLayer.B, 0, detections)
            ```
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
            filter_fn: Acceptance predicate for non-manual candidates; `True`
                includes a box and `None` accepts all. Runs under the store lock.

        Raises:
            ValueError: If `frame_count` is negative.

        Note:
            Existing manual boxes are retained on every frame, including frames with
            no machine detections. Frames outside the requested range are unchanged.
            Every frame in the range is initialized, even when empty. A zero
            count performs no updates; input entries outside the range are ignored.

        !!! warning "No rollback"

            Iteration, predicate, or cloning errors propagate. Earlier frames
            remain updated even though the failing frame is not replaced.

        Examples:
            Given `store`, a `tracked` frame mapping, the video `frame_count`,
            and `VideoDataLayer` imported from `app.domain.video.layer`:

            ```python
            store.replace_machine_boxes_for_frames(VideoDataLayer.D, tracked, frame_count)
            ```
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
            filter_fn: Acceptance predicate; `True` includes a non-manual box.
                `None` accepts all non-manual candidates.

        Note:
            This helper deliberately does not acquire the lock so bulk updates can
            process every frame in one critical section. The caller must hold
            `data_lock`. Manual objects retain their identity; machine objects
            are cloned. Filtering, iteration, and cloning errors propagate
            before assignment.
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

        All four layer keys are included; empty frames are omitted. Serialization
        creates new dictionaries and coordinate lists under one lock acquisition.
        It does not write a file or preserve initialized-empty frame entries.
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
            ValueError: If a layer name, frame-index string, or serialized box
                source cannot be parsed.
            KeyError: If a serialized box is missing a required field.
            TypeError: If a frame key cannot be converted to an integer or box
                coordinates cannot be iterated.

        !!! warning "Loading is not transactional"

            All four layers are cleared before parsing begins. Conversion errors
            propagate and may leave partially loaded data; the old contents are
            not restored. Validate external project data before calling.

        Frame keys are passed to `int()` without checking video bounds. Empty
        lists create initialized entries, omitted layers remain empty, and box
        objects are reconstructed rather than shared with the payload.
        """
        with self.data_lock:
            for layer in VideoDataLayer:
                self._data[layer].clear()

            for layer_name, frames in payload.items():
                layer = VideoDataLayer(layer_name)
                for frame_index, boxes in frames.items():
                    self._data[layer][int(frame_index)] = [dict_to_box(box) for box in boxes]
