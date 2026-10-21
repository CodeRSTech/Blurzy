"""Protocol for frame-indexed annotation storage owned by a video session.

Layer: Application interface.
Context: The application depends on this data-only contract rather than the
infrastructure store; operations address domain layers and per-frame boxes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING



from typing import Protocol
if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from app.domain import VideoDataLayer, ListOfBoxes, ProcessingSettings, BBoxViewModel





class SessionDataStoreInterface(Protocol):
    """Contract for reading and mutating a session's annotation layers.

    Layer: Application interface.
    Context: Defines the storage seam used by application services; the
    backing adapter enforces persistence, locking, and layer mutation rules.
    """

    # ============================== READ ==============================

    def get_boxes_for_layer_at_frame_index_as_list(
        self, layer: VideoDataLayer, frame_index: int
    ) -> ListOfBoxes:
        """Return the boxes stored for one layer and frame.

        Args:
            layer: Domain layer to read.
            frame_index: Zero-based frame whose boxes are requested.

        Returns:
            Boxes for the frame, or an empty list when no frame data exists.
        """
        ...

    def get_all_boxes_for_layer_as_dict_of_lists(self, layer: VideoDataLayer) -> dict[int, ListOfBoxes]:
        """Return all populated frames for a layer as frame-indexed box lists.

        Args:
            layer: Domain layer to read.

        Returns:
            A mapping from frame index to boxes stored on that frame.
        """
        ...

    def has_boxes_for_layer(self, layer: VideoDataLayer) -> bool:
        """Check whether a layer contains any boxes.

        Args:
            layer: Domain layer to inspect.

        Returns:
            ``True`` when at least one box is stored.
        """
        ...

    def has_boxes_for_layer_at_frame_index(self, layer: VideoDataLayer, frame_index: int) -> bool:
        """Check whether a layer contains boxes at a particular frame.

        Args:
            layer: Domain layer to inspect.
            frame_index: Zero-based frame index.

        Returns:
            ``True`` when the frame contains at least one box.
        """
        ...

    def has_frame_for_layer_at_frame_index(self, layer: VideoDataLayer, frame_index: int) -> bool:
        """Check whether a frame entry exists for a layer, even if it is empty.

        Args:
            layer: Domain layer to inspect.
            frame_index: Zero-based frame index.

        Returns:
            ``True`` when storage has an entry for that layer and frame.
        """
        ...

    # ============================== CREATE / UPDATE ==============================

    def add_box_to_layer_at_frame_index(
        self, layer: VideoDataLayer, frame_index: int, box: BBoxViewModel
    ) -> None:
        """Add one box to a layer at the given frame.

        Args:
            layer: Destination domain layer.
            frame_index: Zero-based frame index.
            box: Box view model to store.
        """
        ...

    def add_boxes_to_layer_at_frame_index(
        self, layer: VideoDataLayer, frame_index: int, boxes: Iterable[BBoxViewModel]
    ) -> None:
        """Add multiple boxes to a layer at the given frame.

        Args:
            layer: Destination domain layer.
            frame_index: Zero-based frame index.
            boxes: Boxes to append to the frame's stored annotations.
        """
        ...

    def purge_boxes_in_layer_by_minimum_confidence_at_frame_index(
        self, layer: VideoDataLayer, min_conf: float, frame_index: int
    ) -> None:
        """Remove boxes below a confidence threshold from one frame.

        Args:
            layer: Layer whose frame data is filtered.
            min_conf: Minimum confidence retained.
            frame_index: Zero-based frame index to filter.
        """
        ...

    def move_boxes_in_layer_at_frame_index_by_delta(
        self, layer: VideoDataLayer, frame_index: int, keys: set[str], delta_x: float, delta_y: float
    ) -> int:
        """Translate selected boxes in a frame by a coordinate delta.

        Args:
            layer: Layer containing the selected boxes.
            frame_index: Zero-based frame index.
            keys: Box keys identifying the boxes to move.
            delta_x: Horizontal translation in frame coordinates.
            delta_y: Vertical translation in frame coordinates.

        Returns:
            Number of boxes moved.
        """
        ...

    def move_manual_boxes_in_layer_at_frame_index_by_delta(
        self, layer: VideoDataLayer, frame_index: int, keys: set[str], delta_x: float, delta_y: float
    ) -> int:
        """Translate selected manual boxes while leaving machine boxes unchanged.

        Args:
            layer: Layer containing the selected boxes.
            frame_index: Zero-based frame index.
            keys: Box keys identifying the boxes to move.
            delta_x: Horizontal translation in frame coordinates.
            delta_y: Vertical translation in frame coordinates.

        Returns:
            Number of manual boxes moved.
        """
        ...

    # ============================== DELETE ==============================

    def purge_boxes_in_layer_by_minimum_confidence(self, layer: VideoDataLayer, min_conf: float) -> None:
        """Remove boxes below a confidence threshold from every frame.

        Args:
            layer: Layer whose data is filtered.
            min_conf: Minimum confidence retained.
        """
        ...

    def apply_filters_to_layers(
        self, source_layer_name: VideoDataLayer, target_layer_name: VideoDataLayer, session_settings: ProcessingSettings
    ) -> int:
        """Apply session filtering settings while transferring boxes between layers.

        Args:
            source_layer_name: Layer providing boxes for filtering.
            target_layer_name: Layer receiving retained boxes.
            session_settings: Confidence and processing settings to apply.

        Returns:
            Number of boxes written to the target layer.
        """
        ...

    def clear_all_layers(self, keep_manual: bool = False) -> None:
        """Clear all layer data, optionally retaining manual annotations.

        Args:
            keep_manual: Preserve manually created boxes when ``True``.
        """
        ...

    def clear_layer_by_name(self, layer: VideoDataLayer, keep_manual: bool = False) -> None:
        """Clear one layer, optionally retaining manual annotations.

        Args:
            layer: Layer to clear.
            keep_manual: Preserve manually created boxes when ``True``.
        """
        ...

    def clear_layers_by_name(self, layers: list[VideoDataLayer]) -> None:
        """Clear each named layer.

        Args:
            layers: Domain layers to clear.
        """
        ...

    def delete_boxes_from_layer_by_id(self, layer: VideoDataLayer, box_ids: Iterable[str]) -> None:
        """Delete boxes with matching identifiers throughout a layer.

        Args:
            layer: Layer to update.
            box_ids: Identifiers of boxes to remove.
        """
        ...

    def delete_boxes_from_layer_by_id_at_frame_index(
        self, layer: VideoDataLayer, box_ids: Iterable[str], frame_index: int
    ) -> bool:
        """Delete matching boxes from one frame.

        Args:
            layer: Layer to update.
            box_ids: Identifiers of boxes to remove.
            frame_index: Zero-based frame index.

        Returns:
            Whether at least one matching box was deleted.
        """
        ...

    def overwrite_source_to_target_layer_at_index(
        self, source_layer: VideoDataLayer, target_layer: VideoDataLayer, index: int
    ) -> None:
        """Replace target-layer boxes at one frame with source-layer boxes.

        Args:
            source_layer: Layer whose frame data is copied.
            target_layer: Layer whose frame data is replaced.
            index: Zero-based frame index.
        """
        ...

    def overwrite_source_layer_to_target_layer(
        self,
        source_layer: VideoDataLayer,
        target_layer: VideoDataLayer,
        filter_fn: Callable[[BBoxViewModel], bool] | None = None,
    ) -> None:
        """Replace target-layer content with source boxes, optionally filtered.

        Args:
            source_layer: Layer providing replacement boxes.
            target_layer: Layer whose content is overwritten.
            filter_fn: Optional predicate selecting boxes to copy.
        """
        ...

    def overwrite_layer_with_dict_of_boxes(
        self, layer: VideoDataLayer, boxes_dict: dict[int, ListOfBoxes]
    ) -> None:
        """Replace a layer's complete frame-to-box mapping.

        Args:
            layer: Layer whose stored data is replaced.
            boxes_dict: Replacement boxes keyed by zero-based frame index.
        """
        ...

    def overwrite_layer_at_index_with_boxes(
        self, layer: VideoDataLayer, frame_index: int, boxes: ListOfBoxes
    ) -> None:
        """Replace all boxes for one frame in a layer.

        Args:
            layer: Layer to update.
            frame_index: Zero-based frame index.
            boxes: Replacement box list.
        """
        ...

    def replace_machine_boxes_at_frame_index(
        self,
        layer: VideoDataLayer,
        frame_index: int,
        boxes: Iterable[BBoxViewModel],
        filter_fn: Callable[[BBoxViewModel], bool] | None = None,
    ) -> None:
        """Replace machine output for one frame while preserving manual boxes."""
        ...

    def replace_machine_boxes_for_frames(
        self,
        layer: VideoDataLayer,
        boxes_by_frame: dict[int, ListOfBoxes],
        frame_count: int,
        filter_fn: Callable[[BBoxViewModel], bool] | None = None,
    ) -> None:
        """Refresh machine output over a frame range under one storage lock."""
        ...
