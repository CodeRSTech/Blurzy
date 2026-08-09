"""Unified layer service facade for cross-layer operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from app.application.adapters import ApplicationAdapter
from app.domain import VideoDataLayer, BoxSource, BBoxXYXYTuple, str_iterable_as_set_without_null_values, \
    VideoDataLayerGroup, Direction, FrameBoxesViewModel, BBoxViewModel
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
    from collections.abc import Iterable
    from app.application.application import Application
    from app.domain.session import SessionId
    from app.infrastructure.session.session import Session

logger = get_logger("Application->UnifiedLayerService")


@final
class UnifiedLayerService:
    """
    Facade service that coordinates operations across all four detection layers.

    Responsibilities:

    - Route operations to the appropriate layer service (Detection or Tracking).
    - Provide a unified interface for layer-agnostic operations.
    - Handle lazy seeding of editable layers from immutable sources.
    - Prevent operations on immutable layers (A, C).
    - Implement Just-In-Time (JIT) layer population.

    Note:
        - Delegates to ``DetectionLayerService`` for ``DataLayer.B``/``DataLayer.A`` operations.
        - Delegates to ``TrackingLayerService`` for ``DataLayer.D``/``DataLayer.C`` operations.
        - Does operations by itself for redundant tasks (e.g., copying boxes between frames).
        - Implements JIT seeding: only populate editable layers when accessed.
        - Protects immutable layers from user modifications.

        Just-In-Time Seeding:

        - When a user opens the`Detection` tab → seed ``DataLayer.B`` from ``DataLayer.A`` on-demand.
        - When a user opens the `Tracking` tab → seed ``DataLayer.D`` from ``DataLayer.C`` on-demand.
        - Saves memory and avoids redundant processing.
        - User edits to B/D are persistent (don't re-seed on next access).

        Layer Mapping:

        - `Detection` Tab ↔ ``DataLayer.B`` (editable, seeded from ``DataLayer.A``).
        - `Tracking` Tab ↔ ``DataLayer.D`` (editable, seeded from ``DataLayer.C``).
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
        Refilter layer ``DataLayer.B`` or ``DataLayer.D`` based on current session settings.

        Args:
            layer_name (VideoDataLayer): Layer to apply filters to (``DataLayer.B`` or ``DataLayer.D``).
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
            layer_name (VideoDataLayer): Layer to copy from (``DataLayer.B`` or ``DataLayer.D``).
            item_keys (Iterable[str]): Iterable of detection keys to copy.
            direction (Direction): ``Direction.NEXT`` or ``Direction.PREV``.

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
            tab (VideoDataLayerGroup): ``DataBox.DETECTION`` or ``DataBox.TRACKING``.

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

    def get_tab_frame_boxes_for_session_id(self, s_id: SessionId, tab: VideoDataLayerGroup) -> FrameBoxesViewModel:
        session = self._app_adapter.get_session_by_id(s_id)
        frame_index = session.state.playback.current_frame_index

        if tab == VideoDataLayerGroup.DETECTION:
            # Seed Layer B from Layer A Just-In-Time
            _seed_layer_frame_from_layer(
                source=VideoDataLayer.A, target=VideoDataLayer.B, session=session, frame_index=frame_index
            )
            boxes = session.data.get_boxes_for_layer_at_frame_index_as_list(VideoDataLayer.B, frame_index)
        elif tab == VideoDataLayerGroup.TRACKING:
            # Seed Layer D from Layer C Just-In-Time
            _seed_layer_frame_from_layer(
                source=VideoDataLayer.C, target=VideoDataLayer.D, session=session, frame_index=frame_index
            )
            boxes = session.data.get_boxes_for_layer_at_frame_index_as_list(VideoDataLayer.D, frame_index)
        else:
            raise UnsupportedTabException(tab)

        return FrameBoxesViewModel(frame_data_boxes=boxes)

    def get_layer_box_by_key(
            self, s_id: SessionId, layer_name: VideoDataLayer, key: str
    ) -> BBoxViewModel | None:
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
        if layer_name == VideoDataLayer.A or layer_name == VideoDataLayer.C:
            raise ImmutableLayerOperationException("reset_frame_for_layer", layer_name)
        elif layer_name == VideoDataLayer.B or layer_name == VideoDataLayer.D:
            # ============================================================
            # Get session
            # ============================================================
            session = self._app_adapter.get_session_by_id(s_id)

            if layer_name == VideoDataLayer.B:
                # ============================================================
                # Overwrite layer B with layer A at the specified frame index
                # ============================================================
                session.data.overwrite_source_to_target_layer_at_index(VideoDataLayer.A, VideoDataLayer.B, frame_index)

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

    def change_xyxy_for_boxes_at_current_idx_by_keys_and_dxdy(self, s_id, layer_name, item_keys, dx, dy) -> int:
        # ============================================================
        # Get session
        # ============================================================
        session = self._app_adapter.get_session_by_id(s_id)

        keys = str_iterable_as_set_without_null_values(item_keys)

        # [NOTE]
        # `DataStore` manages all CRUD operations for layers
        # It should be responsible for all updating the boxes at an index.
        # (or even the entire layer if need be)

        moved = session.data.move_manual_boxes_in_layer_at_frame_index_by_delta(
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
        session = self._app_adapter.get_session_by_id(s_id)

        frame_index = session.state.playback.current_frame_index

        boxes = session.data.get_boxes_for_layer_at_frame_index_as_list(layer_name, frame_index)

        item = next((i for i in boxes if i.key == item_key), None)
        if item is None:
            raise UnknownFrameItemException(item_key)

        item.label = label
        item.bbox_xyxy = bbox_xyxy

        logger.info("Updated item {} in session_state {} frame {}", item_key, s_id, frame_index)


def _seed_layer_frame_from_layer(
        source: VideoDataLayer, target: VideoDataLayer, session: Session, frame_index: int
) -> None:
    """Just-In-Time (JIT) Seeder: Lazily populates Layer B only when the user looks at it."""
    logger.trace("Seeding Layer {} from Layer {} for frame {}", target, source, frame_index)

    # FAST CHECK: If Layer B already has data for this frame, skip.
    if session.data.has_boxes_for_layer_at_frame_index(target, frame_index):
        logger.trace("Layer {} already has data for frame {}", target, frame_index)
        return

    # FAST CHECK: If Layer A is empty for this frame, skip.
    if not session.data.has_boxes_for_layer_at_frame_index(source, frame_index):
        logger.trace("Layer {} is empty for frame {}", source, frame_index)
        return

    # HEAVY LIFT: Fetch the pristine AI boxes from Layer A
    raw_boxes = session.data.get_boxes_for_layer_at_frame_index_as_list(source, frame_index)

    # Clone them instantly so manual edits in Layer B don't break Layer A
    copied_boxes = [box.clone() for box in raw_boxes]

    # Inject into Layer B
    logger.trace(
        "Injecting {} boxes into Layer {} data for frame {}", len(copied_boxes), target, frame_index
    )
    session.data.add_boxes_to_layer_at_frame_index(target, frame_index, copied_boxes)
