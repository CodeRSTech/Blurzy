"""
Unified layer service facade for cross-layer operations.

See Also:
    - [`DetectionLayerService`][app.application.services.detection.layer.DetectionLayerService] — manages detection-layer operations
    - [`TrackingLayerService`][app.application.services.tracking.layer_service.TrackingLayerService] — manages tracking-layer operations

Layer: Application.
Context: Coordinates domain state and infrastructure to complete application use cases.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from app.application.adapters import ApplicationAdapter
from app.application.services.helpers.layer_seeding import seed_layer_frame_from_layer
from app.domain import VideoDataLayer, BoxSource, str_iterable_as_set_without_null_values, VideoDataLayerGroup, Direction, FrameBoxesViewModel
from app.domain.views.bounding_box_view_model import BBoxViewModel
from app.domain.helpers.functions import new_passes_filter
from app.shared import get_logger
from app.shared.exceptions import (
    ImmutableLayerOperationException,
    UnknownFrameItemException,
    UnsupportedDirectionException,
    UnsupportedLayerOperationException,
    UnsupportedTabException,
)
if TYPE_CHECKING:
    from app.domain import BBoxXYXYTuple


if TYPE_CHECKING:
    from collections.abc import Iterable
    from app.application.application import Application
    from app.domain.session import SessionId

logger = get_logger("Application->UnifiedLayerService")


@final
class UnifiedLayerService:
    """
    Facade service that coordinates operations across all four detection layers.

    Responsibilities:

    - Route operations to the appropriate layer service (Detection or Tracking).
    - Provide a unified interface for layer-agnostic operations.
    - Handle compatibility seeding of editable layers from immutable sources.
    - Prevent operations on immutable layers (A, C).
    - Seed editable layers eagerly for new results and lazily for older sessions.

    Note:
        - Delegates to `DetectionLayerService` for `DataLayer.B`/`DataLayer.A` operations.
        - Delegates to `TrackingLayerService` for `DataLayer.D`/`DataLayer.C` operations.
        - Does operations by itself for redundant tasks (e.g., copying boxes between frames).
        - Retains JIT seeding as a compatibility path for sessions with older data.
        - Protects immutable layers from user modifications.

        Layer Seeding:

        - Older sessions seed missing `DataLayer.B` frames from `DataLayer.A` on-demand.
        - Older sessions seed missing `DataLayer.D` frames from `DataLayer.C` on-demand.
        - User edits to B/D are persistent (don't re-seed on next access).

        Layer Mapping:

        - `Detection` Tab ↔ `DataLayer.B` (editable, seeded from `DataLayer.A`).
        - `Tracking` Tab ↔ `DataLayer.D` (editable, seeded from `DataLayer.C`).



    Args:
        app: Application providing detection/tracking layer services and session access for this facade.
    """

    def __init__(self, app: Application):
        # self._app = app
        self._app_adapter = ApplicationAdapter(app)
        self.detection_layer_svc = app.detection_layer_svc
        self.tracking_layer_svc = app.tracking_layer_svc

    # [AUDIT] DEAD CODE: 17-line commented method blocks code readability
    # This appears to be an alternative implementation that was superseded by apply_filters_to_layer_by_layer().
    # Recommendation: Remove completely and rely on git history if recovery is needed.
    # Leaving dead code creates confusion about which API is canonical and maintenance burden.
    # def apply_filters_to_layer_by_box_group(self, box_group: DataBoxGroup, s_id: SessionId) -> int:
    #     """
    #     Refilter layer ``DataLayer.B`` or ``DataLayer.D`` based on current session settings.
    #
    #     Args:
    #         box_group (DataBoxGroup): Box type to apply filters to (``DataBox.DETECTION`` or ``DataBox.TRACKING``).
    #         s_id (SessionId): Session ID.
    #
    #     Returns:
    #         int: Number of frames where filtering changed the detection count.
    #
    #     """
    #     # [NOTE] This method replaces the previous `apply_filters_to_layer_b` method.
    #
    #     if box_group == DataBoxGroup.DETECTION:
    #         source_layer_name = DataLayer.A
    #         target_layer_name = DataLayer.B
    #     elif box_group == DataBoxGroup.TRACKING:
    #         source_layer_name = DataLayer.C
    #         target_layer_name = DataLayer.D
    #     else:
    #         raise ValueError(f"Unsupported detection group: {box_group}")
    #     session = self._app_adapter.get_session_by_id(s_id)
    #
    #     changed_frames = session.data.apply_filters_to_layers(
    #         source_layer_name=source_layer_name,
    #         target_layer_name=target_layer_name,
    #         session_settings=session.view_state.settings
    #     )
    #
    #     return changed_frames

    def apply_filters_to_layer_by_layer(self, layer_name: VideoDataLayer, s_id: SessionId) -> int:
        """
        Refilter layer `DataLayer.B` or `DataLayer.D` based on current session settings.

        Args:
            layer_name (VideoDataLayer): Layer to apply filters to (`DataLayer.B` or `DataLayer.D`).
            s_id (SessionId): Session ID.

        Returns:
            int: Number of frames where filtering changed the detection count.

        """
        # [NOTE] This method replaces the previous `apply_filters_to_layer_b` method.

        if layer_name == VideoDataLayer.B:
            source_layer_name = VideoDataLayer.A
        elif layer_name == VideoDataLayer.D:
            source_layer_name = VideoDataLayer.C
        else:
            raise UnsupportedLayerOperationException("apply_filters_to_layer_by_layer", layer_name)
        session = self._app_adapter.get_session_by_id(s_id)

        changed_frames = session.data.apply_filters_to_layers(
            source_layer_name=source_layer_name,
            target_layer_name=layer_name,
            session_settings=session.state.settings
        )

        return changed_frames

    def copy_boxes_to_adjacent_frame_by_direction(
            self, s_id: SessionId, layer_name: VideoDataLayer, item_keys: Iterable[str], direction: Direction
    ) -> None:
        """
        Copy boxes to the adjacent frame (next or previous).

        Args:
            s_id (SessionId): Session ID.
            layer_name (VideoDataLayer): Layer to copy from (`DataLayer.B` or `DataLayer.D`).
            item_keys (Iterable[str]): Iterable of detection keys to copy.
            direction (Direction): `Direction.NEXT` or `Direction.PREV`.

        Raises:
            ValueError: If the layer is immutable (A or C) or direction is unsupported.
        """
        # ============================================================
        # Preprocessing and safety checks
        # ============================================================
        if layer_name not in (VideoDataLayer.B, VideoDataLayer.D):
            raise UnsupportedLayerOperationException("copy_boxes_to_adjacent_frame_by_direction", layer_name)

        keys = str_iterable_as_set_without_null_values(item_keys)
        session = self._app_adapter.get_session_by_id(s_id)

        current_idx = session.state.playback.current_frame_index
        if direction == Direction.NEXT:
            target_idx = min(current_idx + 1, max(session.state.metadata.frame_count - 1, 0))
        elif direction == Direction.PREV:
            target_idx = max(current_idx - 1, 0)
        else:
            raise UnsupportedDirectionException(direction)

        if target_idx == current_idx:
            return

        # ====================================================================
        # 3. GET CURRENT FRAME BOXES
        # ====================================================================
        source_boxes = session.data.get_boxes_for_layer_at_frame_index_as_list(layer_name, current_idx)

        # ====================================================================
        # 4. FILTER TO SELECTED KEYS AND VALIDATE NON-EMPTY
        # ====================================================================
        # [INFO] Use clone() to create new instances of boxes to copy,
        #        so that we don't modify the original boxes in the source frame.
        to_copy = [i.clone() for i in source_boxes if i.key in keys]
        if not to_copy:
            return

        # ====================================================================
        # 5. MODIFY BOXES TO COPY IN PLACE WITH NEW IDS, SOURCE AND KEYS
        # ====================================================================
        # [NEW] Modify the boxes in place to have new IDs, source,
        #       and keys for the target frame.
        for box in to_copy:
            box.id = f"manual-{session.state.next_annotation_id}"
            box.source = BoxSource.MANUAL
            box.key = f"manual:manual-{session.state.next_annotation_id}"

            session.state.next_annotation_id += 1

        # ====================================================================
        # 6. COPY BOXES WITH NEW IDS TO TARGET FRAME
        # ====================================================================
        session.data.add_boxes_to_layer_at_frame_index(layer_name, target_idx, to_copy)

        logger.info(
            "Duplicated {} item(s) from frame {} to frame {} for session '{}'",
            len(to_copy),
            current_idx,
            target_idx,
            s_id,
        )

    def delete_boxes_by_keys_and_tab_id_for_current_frame_by_session_id(
            self, s_id: SessionId, keys: list[str], tab: VideoDataLayerGroup
    ) -> None:
        """
        Delete boxes from the current frame in the active tab (Detection or Tracking).

        Args:
            s_id (SessionId): Session ID.
            keys (list[str]): List of detection keys to delete.
            tab (VideoDataLayerGroup): `DataBox.DETECTION` or `DataBox.TRACKING`.

        """
        if tab == VideoDataLayerGroup.TRACKING:
            layer_name = VideoDataLayer.D
        else:
            layer_name = VideoDataLayer.B

        # ============================================================
        # Get session
        # ============================================================
        session = self._app_adapter.get_session_by_id(s_id)

        keys = str_iterable_as_set_without_null_values(keys)

        session.data.delete_boxes_from_layer_by_id_at_frame_index(
            layer_name, keys, session.state.playback.current_frame_index)

    def add_manual_boxes_to_current_frame(
            self,
            s_id: SessionId,
            tab: VideoDataLayerGroup,
            boxes: Iterable[tuple[str, BBoxXYXYTuple, str]],
    ) -> list[str]:
        """
        Create clipboard boxes as manual boxes in Detection or Tracking editable layers.

        Args:
            s_id: Identifier of the session receiving the boxes.
            tab: Detection or tracking tab, selecting editable layer B or D.
            boxes: Tuples of `(label, coordinates, color_hex)` for new boxes.

        Returns:
            Keys assigned to the newly created manual boxes.
        """
        layer_name = VideoDataLayer.B if tab == VideoDataLayerGroup.DETECTION else VideoDataLayer.D
        session = self._app_adapter.get_session_by_id(s_id)
        frame_index = session.state.playback.current_frame_index
        created: list[BBoxViewModel] = []
        for label, bbox_xyxy, color_hex in boxes:
            annotation_id = session.state.next_annotation_id
            created.append(
                BBoxViewModel(
                    id=f"manual-{annotation_id}",
                    source=BoxSource.MANUAL,
                    label=label,
                    bbox_xyxy=bbox_xyxy,
                    color_hex=color_hex,
                    confidence=1.0,
                    key=f"manual:manual-{annotation_id}",
                )
            )
            session.state.next_annotation_id += 1

        if created:
            session.data.add_boxes_to_layer_at_frame_index(layer_name, frame_index, created)
        logger.debug("Pasted {} manual boxes into layer {} frame {}.", len(created), layer_name, frame_index)
        logger.trace("Pasted box keys: {}", [box.key for box in created])
        return [box.key for box in created]

    def replace_tab_frame_boxes(
            self,
            s_id: SessionId,
            tab: VideoDataLayerGroup,
            frame_index: int,
            boxes: list[BBoxViewModel],
    ) -> None:
        """
        Replace one editable frame with cloned history snapshot boxes.

        Args:
            s_id: Identifier of the session whose frame is being restored.
            tab: Detection or tracking tab selecting editable layer B or D.
            frame_index: Zero-based frame index to replace.
            boxes: Snapshot boxes to clone into that frame.
        """
        layer_name = VideoDataLayer.B if tab == VideoDataLayerGroup.DETECTION else VideoDataLayer.D
        session = self._app_adapter.get_session_by_id(s_id)
        session.data.overwrite_layer_at_index_with_boxes(layer_name, frame_index, [box.clone() for box in boxes])
        logger.debug("Restored {} boxes into layer {} frame {}.", len(boxes), layer_name, frame_index)

    def get_tab_frame_boxes_at_frame_index(
            self, s_id: SessionId, tab: VideoDataLayerGroup, frame_index: int
    ) -> list[BBoxViewModel]:
        """
        Return cloned editable-layer boxes without changing playback state.

        Args:
            s_id: Identifier of the session to query.
            tab: Detection or tracking tab selecting editable layer B or D.
            frame_index: Zero-based frame index to query.

        Returns:
            Clones of the boxes stored in the selected editable layer and frame.
        """
        layer_name = VideoDataLayer.B if tab == VideoDataLayerGroup.DETECTION else VideoDataLayer.D
        session = self._app_adapter.get_session_by_id(s_id)
        return [
            box.clone()
            for box in session.data.get_boxes_for_layer_at_frame_index_as_list(layer_name, frame_index)
        ]

    def get_tab_frame_boxes_for_session_id(self, s_id: SessionId, tab: VideoDataLayerGroup) -> FrameBoxesViewModel:
        """
        Return boxes for the session's current frame in the selected tab.

        Args:
            s_id: Identifier of the session to query.
            tab: Detection or tracking tab to read.

        Returns:
            View model containing boxes from editable layer B or D.

        Raises:
            UnsupportedTabException: If `tab` is not a supported data tab.

        Note:
            When an editable-layer frame has not yet been initialized, it may
            be seeded from its corresponding source layer (A or C).
        """
        session = self._app_adapter.get_session_by_id(s_id)
        frame_index = session.state.playback.current_frame_index

        if tab == VideoDataLayerGroup.DETECTION:
            # Compatibility seeding for Layer B frames not initialized by detection.
            seed_layer_frame_from_layer(
                source=VideoDataLayer.A, target=VideoDataLayer.B, session=session, frame_index=frame_index
            )
            boxes = session.data.get_boxes_for_layer_at_frame_index_as_list(VideoDataLayer.B, frame_index)
        elif tab == VideoDataLayerGroup.TRACKING:
            # Compatibility seeding for Layer D frames not initialized by tracking.
            seed_layer_frame_from_layer(
                source=VideoDataLayer.C, target=VideoDataLayer.D, session=session, frame_index=frame_index
            )
            boxes = session.data.get_boxes_for_layer_at_frame_index_as_list(VideoDataLayer.D, frame_index)
        else:
            raise UnsupportedTabException(tab)

        return FrameBoxesViewModel(frame_data_boxes=boxes)

    def get_layer_box_by_key(
            self, s_id: SessionId, layer_name: VideoDataLayer, key: str
    ) -> BBoxViewModel | None:
        """
        Find a box by key in the specified layer at the current frame.

        Args:
            s_id: Identifier of the session to query.
            layer_name: Editable layer B or D to search.
            key: Unique key of the box to find.

        Returns:
            Matching box view model, or `None` when no box has that key.

        Raises:
            UnsupportedLayerOperationException: If `layer_name` is immutable or unsupported.
        """
        if layer_name == VideoDataLayer.B or layer_name == VideoDataLayer.D:
            # ============================================================
            # Get session
            # ============================================================
            session = self._app_adapter.get_session_by_id(s_id)

            frame_index = session.state.playback.current_frame_index
            boxes = session.data.get_boxes_for_layer_at_frame_index_as_list(layer_name, frame_index)

            return next((i for i in boxes if i.key == key), None)
        else:
            raise UnsupportedLayerOperationException("get_layer_box_by_key", layer_name)

    def reset_all_for_layer(self, s_id: SessionId, layer_name: VideoDataLayer) -> None:
        """
        Rebuild an editable layer from its source layer across all frames.

        Args:
            s_id: Identifier of the session to update.
            layer_name: Editable layer B or D to rebuild from A or C.

        Raises:
            ImmutableLayerOperationException: If the requested layer is immutable.
            UnsupportedLayerOperationException: If the layer is unsupported.
        """
        if layer_name == VideoDataLayer.A or layer_name == VideoDataLayer.C:
            raise ImmutableLayerOperationException("reset_all_for_layer", layer_name)
        elif layer_name == VideoDataLayer.B or layer_name == VideoDataLayer.D:
            if layer_name == VideoDataLayer.B:
                source_layer_name = VideoDataLayer.A
            else:
                source_layer_name = VideoDataLayer.C

            # ============================================================
            # Get session
            # ============================================================
            session = self._app_adapter.get_session_by_id(s_id)

            # ============================================================
            # Overwrite layer whilst actively filtering by filter_fn
            # ============================================================

            session.data.overwrite_source_layer_to_target_layer(
                source_layer_name,
                layer_name,
                filter_fn=lambda box: new_passes_filter(layer_name, box, session.state.settings)
            )
            logger.info("Reset all frames for layer {} for session '{}'", layer_name, s_id)

        else:
            raise UnsupportedLayerOperationException("reset_all_for_layer", layer_name)

    def reset_frame_for_layer(self, s_id: SessionId, layer_name: VideoDataLayer, frame_index: int) -> None:
        """
        Rebuild one editable-layer frame from its corresponding source frame.

        Args:
            s_id: Identifier of the session to update.
            layer_name: Editable layer B or D to rebuild.
            frame_index: Zero-based frame index to reset.

        Raises:
            ImmutableLayerOperationException: If the requested layer is immutable.
            UnsupportedLayerOperationException: If the layer is unsupported.
        """
        if layer_name == VideoDataLayer.A or layer_name == VideoDataLayer.C:
            raise ImmutableLayerOperationException("reset_frame_for_layer", layer_name)
        elif layer_name == VideoDataLayer.B or layer_name == VideoDataLayer.D:
            # ============================================================
            # Get session
            # ============================================================
            session = self._app_adapter.get_session_by_id(s_id)

            if layer_name == VideoDataLayer.B:
                # ============================================================
                # Overwrite layer B with currently filtered Layer A boxes
                # ============================================================
                source_boxes = session.data.get_boxes_for_layer_at_frame_index_as_list(
                    VideoDataLayer.A, frame_index
                )
                filtered_boxes = [
                    box.clone()
                    for box in source_boxes
                    if new_passes_filter(VideoDataLayer.B, box, session.state.settings)
                ]
                session.data.overwrite_layer_at_index_with_boxes(
                    VideoDataLayer.B, frame_index, filtered_boxes
                )

            if layer_name == VideoDataLayer.D:
                # ============================================================
                # Overwrite layer D with layer C at the specified frame index
                # ============================================================
                session.data.overwrite_source_to_target_layer_at_index(VideoDataLayer.C, VideoDataLayer.D, frame_index)
                # ============================================================
                # Purge boxes that fall below min tracker confidence
                # ============================================================
                session.data.purge_boxes_in_layer_by_minimum_confidence_at_frame_index(
                    VideoDataLayer.D, session.state.settings.min_tracker_confidence, frame_index
                )
        else:
            raise UnsupportedLayerOperationException("reset_frame_for_layer", layer_name)

    def change_xyxy_for_boxes_at_current_idx_by_keys_and_dxdy(
        self, s_id: SessionId, layer_name: VideoDataLayer, item_keys: Iterable[str], dx: int, dy: int
    ) -> int:
        # ============================================================
        # Get session
        # ============================================================
        """
        Translate selected boxes on the current frame by a pixel offset.

        Args:
            s_id: Identifier of the session to update.
            layer_name: Editable layer containing the boxes.
            item_keys: Keys of the boxes to move.
            dx: Horizontal translation in pixels.
            dy: Vertical translation in pixels.

        Returns:
            Number of boxes moved.
        """
        session = self._app_adapter.get_session_by_id(s_id)

        keys = str_iterable_as_set_without_null_values(item_keys)

        # [NOTE]
        # `DataStore` manages all CRUD operations for layers
        # It should be responsible for all updating the boxes at an index.
        # (or even the entire layer if need be)

        moved = session.data.move_boxes_in_layer_at_frame_index_by_delta(
            layer_name, session.state.playback.current_frame_index, keys, dx, dy
        )
        return moved

    def update_current_frame_box_xyxy(self,
                                      s_id: SessionId,
                                      layer_name: VideoDataLayer,
                                      item_key: str,
                                      label: str,
                                      bbox_xyxy: BBoxXYXYTuple,
                                      ) -> None:
        """
        Update a box's label and coordinates on the current frame.

        Args:
            s_id: Identifier of the session containing the box.
            layer_name: Layer containing the box.
            item_key: Unique key identifying the box.
            label: Replacement classification label.
            bbox_xyxy: Replacement `(x1, y1, x2, y2)` coordinates.

        Raises:
            UnknownFrameItemException: If no box with `item_key` exists on the current frame.
        """
        session = self._app_adapter.get_session_by_id(s_id)

        frame_index = session.state.playback.current_frame_index

        boxes = session.data.get_boxes_for_layer_at_frame_index_as_list(layer_name, frame_index)

        item = next((i for i in boxes if i.key == item_key), None)
        if item is None:
            raise UnknownFrameItemException(item_key)

        item.label = label
        item.bbox_xyxy = bbox_xyxy

        logger.info("Updated item {} in session_state {} frame {}", item_key, s_id, frame_index)
