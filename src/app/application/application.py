from __future__ import annotations

from typing import final, override, TYPE_CHECKING

from PySide6.QtCore import QObject

from app.application.managers import SessionManager
from app.application import services
from app.application.services.helpers.layer_coercion import ensure_import_mode, ensure_layer_enum
if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from typing import Unpack


if TYPE_CHECKING:
    from app.domain import BBoxXYXYTuple, VideoDataLayer, VideoDataLayerGroup, SessionId, Direction, BBoxViewModel, \
        FrameBoxesViewModel, SessionSettingsViewModel, ProcessingSettingsKwargs
    from app.infrastructure.session.session import Session
    from app.infrastructure.dtypes import RGBFrame


@final
class Application(QObject):
    """
    Thin delegation façade for the entire application layer.

    Responsibilities:
        - Owns all service instances (Detection, Tracking, Export, Session, Layer management).
        - Delegates all calls to the appropriate service without adding business logic.
        - Provides a single entry point for the UI Controller to interact with the application.
        - Manages the ``SessionManager`` for session lifecycle and view_state tracking.

    Note:
        Design pattern:
            This class acts as a Façade — every method is a direct pass-through to a service.
            No logic should live here; all decisions belong in services.
            The UI Controller imports and calls only this class (not individual services).
    """

    def __init__(self) -> None:
        """Initialize the application with all service instances."""
        super().__init__()

        from app.shared.logging_cfg import get_logger

        logger = get_logger("Application->App")
        logger.debug("Initializing App...")

        # ====================================================================
        # 1. INITIALIZE SESSION MANAGER
        # ====================================================================
        self.sm = SessionManager(self)

        # ====================================================================
        # 2. INITIALIZE ALL SERVICES
        # ====================================================================
        self.detection_svc = services.DetectionService(self)
        self.detection_layer_svc = services.DetectionLayerService(self)
        self.tracking_svc = services.TrackingService(self)
        self.tracking_layer_svc = services.TrackingLayerService(self)
        self.export_svc = services.ExportService(self)
        self.session_svc = services.SessionService(self)
        self.unified_layer_svc = services.UnifiedLayerService(self)

        # ====================================================================
        # 3. INITIALIZE IMPORT / EXPORT SERVICES
        # ====================================================================
        # Detection import/export operates on layers A and B.
        # Tracking  import/export operates on layers C and D.
        # Both pairs share the same wire format (_layer_io) so cross-layer
        # import (e.g. A → C) is also possible via the dialog.
        self.detection_import_svc = services.DetectionImportService(self)
        self.detection_export_svc = services.DetectionExportService(self)
        self.tracking_import_svc = services.TrackingImportService(self)
        self.tracking_export_svc = services.TrackingExportService(self)

        logger.debug("App initialized.")

    @override
    def __repr__(self) -> str:
        """Return a concise representation of the App instance."""
        return "Application()"

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
    #                            PROPERTIES
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

    @property
    def active_session(self) -> Session | None:
        """Retrieve the currently active ``Session`` instance, or ``None`` if no session is active."""
        return self.sm.active_session

    @property
    def active_session_id(self) -> SessionId | None:
        """Retrieve the ``SessionId`` of the currently active session, or ``None`` if none is active."""
        return self.sm.active_session_id

    @active_session_id.setter
    def active_session_id(self, s_id: SessionId) -> None:
        """Set the active session by ``SessionId``."""
        self.sm.active_session_id = s_id

    @property
    def all_s_ids(self) -> Iterable[SessionId]:
        """Iterate over all ``SessionId`` instances currently managed by the application."""
        return self.sm.all_session_ids

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
    #                       SESSION MANAGER DELEGATION METHODS
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

    # Used by UIController
    def close(self) -> None:
        """Close all active sessions and shut down the ``SessionManager``."""
        self.sm.close_all()

    # Used by SessionService
    def open_video_from_path(self, path: str) -> None:
        """Open a video file and create a new session from ``path``."""
        self.sm.create_session_from_video_path(path)

    # Used by SessionService
    def initialize_active_session(self) -> None:
        """Set the first available session as the active session."""
        self.sm.initialize_active_session()

    # Used by SessionHandler
    def get_session_settings(self, s_id: SessionId) -> SessionSettingsViewModel:
        """
        Retrieve the ``SessionSettingsViewModel`` for the session specified by ``s_id``.

        NOTE: ``ProcessingSettings`` and ``SessionSettingsViewModel`` intentionally differ:
            - ``ProcessingSettings.chosen_labels`` → ``list[str]``
            - ``SessionSettingsViewModel.chosen_labels`` → ``str`` (comma-separated, UI-ready)
        These are converted via ``ProcessingSettings.as_view_model()``.
        """
        return self.sm.get_session_by_id(s_id).state.settings.as_view_model()

    # Used by PlaybackHandler
    def get_session_frame_interval_ms(self, s_id: SessionId) -> int:
        """Calculate and return the frame interval in milliseconds for ``s_id``."""
        return self.sm.get_session_state_by_id(
            s_id
        ).metadata.calculate_interval_in_mas()

    # Used by AnnotationHandler, DetectionHandler, and UIHandler
    def get_session_by_id(self, s_id: SessionId) -> Session:
        """Fetch the ``Session`` instance identified by ``s_id``."""
        return self.sm.get_session_by_id(s_id)

    # Used by PlaybackHandler
    def is_at_last_frame(self, s_id: SessionId) -> bool:
        """Check if the playback position for ``s_id`` is at the final frame."""
        return self.sm.get_session_state_by_id(s_id).is_at_last_frame

    # Used by PlaybackHandler
    def is_session_playing(self, s_id: SessionId) -> bool:
        """Check if the ``Session`` identified by ``s_id`` is currently playing."""
        return self.sm.get_session_state_by_id(s_id).playback.is_playing

    # Used by PlaybackHandler
    def load_frame_by_index(self, s_id: SessionId, frame_index: int) -> RGBFrame | None:
        """Load a specific frame by ``frame_index`` for the session ``s_id``."""
        self.sm.get_frame_for_session_id_by_index(frame_index, s_id)

    # Used by PlaybackHandler
    def load_next_frame(self, s_id: SessionId) -> RGBFrame | None:
        """Advance to and load the next frame in the ``Session`` identified by ``s_id``."""
        self.sm.get_next_frame_for_session_id(s_id)

    # Used by PlaybackHandler (only usage so far)
    def load_previous_frame(self, s_id: SessionId) -> RGBFrame | None:
        """Rewind to and load the previous frame in the ``Session`` identified by ``s_id``."""
        self.sm.get_previous_frame_for_session_id(s_id)

    def set_session_state_is_playing(self, s_id: SessionId, is_playing: bool) -> None:
        """Set the playback view_state (playing/paused) for the session ``s_id``."""
        self.sm.get_session_state_by_id(s_id).playback.is_playing = is_playing

    # Used by PlaybackHandler and SessionHandler
    def stop_all_playback(self) -> None:
        """Stop playback for **all** active sessions."""
        self.sm.stop_all_playback()

    # Used by DetectionHandler, ExportHandler, ModelHandler, and TrackingHandler
    def update_session_settings(
            self, s_id: SessionId, **kwargs: Unpack[ProcessingSettingsKwargs]
    ) -> None:
        """Update processing settings for the session ``s_id`` with keyword arguments."""
        self.session_svc.update_session_settings(s_id, **kwargs)

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
    #                   DETECTION LAYER SERVICE DELEGATION METHODS
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

    # Used by DetectionHandler
    def apply_filters_to_layer(self, layer_name: VideoDataLayer, s_id: SessionId) -> None:
        """
        Apply confidence and size filters
        to
        ``DataLayer.B``(reviewed detections) or ``DataLayer.D``(reviewed tracks)
        for
        ``s_id``.
        """

        # [AUDIT] NAMING CLARITY: Method name is ambiguous
        # `apply_filters_to_layer` doesn't convey which filters (confidence? size? both?).
        # Recommendation: Rename to `apply_confidence_and_size_filters_to_layer()`
        # This makes the intent explicit and helps callers understand what happens.
        # This improves code readability and reduces documentation burden.

        self.unified_layer_svc.apply_filters_to_layer_by_layer(layer_name, s_id)

    # Used by AnnotationHandler
    def add_manual_detection_box_at_current_frame_index(
            self,
            s_id: SessionId,
            label: str,
            bbox_xyxy: BBoxXYXYTuple,
            color_hex: str = "#00ff00",
    ) -> None:
        """Add a manually drawn bounding detection to Layer B (reviewed detections) for the current frame."""
        # [INFO] Although a reasonable candidate for UnifiedLayerService,
        # this method is intentionally kept in DetectionLayerService to maintain separation of concerns.
        # a few of them are:
        #  1. Adding boxes on layer D directly isn't supported yet. The idea is to do the drawing
        #     on layer B and then apply tracking to see how it goes
        #  2. The UI is designed to add boxes to layer B, not layer D. So,
        #     this method is more aligned with the current UI design.
        #  3. It might require more than just name changes and
        #     signature changes to move this method to UnifiedLayerService.
        #     It might require a more significant refactor of the services and how they interact with each other.
        self.detection_layer_svc.add_manual_box_to_layer_b_at_current_frame_index(
            s_id, label, bbox_xyxy, color_hex
        )

    # Used by AnnotationHandler
    def update_box_in_layer_at_current_frame(
            self,
            s_id: SessionId,
            layer_name: VideoDataLayer,
            box_key: str,
            label: str,
            bbox_xyxy: BBoxXYXYTuple,
    ) -> None:
        """Update a bounding detection's label and coordinates in the specified ``layer_name``."""
        self.unified_layer_svc.update_current_frame_box_xyxy(s_id, layer_name, box_key, label, bbox_xyxy)

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
    #               UNIFIED LAYER SERVICE DELEGATION METHODS
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

    # Used by AnnotationHandler
    def change_current_layer_boxes_by_keys_and_dxdy(self, s_id: SessionId, layer_name: VideoDataLayer,
                                                    box_keys: Iterable[str], dx: int, dy: int) -> int:
        """Translate bounding boxes in the specified ``layer_name`` by ``dx`` and ``dy`` pixels; return count moved."""
        return self.unified_layer_svc.change_xyxy_for_boxes_at_current_idx_by_keys_and_dxdy(
            s_id, layer_name, box_keys, dx, dy
        )

    # Used by AnnotationHandler
    def copy_boxes_to_adjacent_frame_by_direction(
            self,
            s_id: SessionId,
            layer_name: VideoDataLayer,
            item_keys: Iterable[str],
            direction: Direction,
    ) -> None:
        """Duplicate bounding boxes to the adjacent frame in the specified ``direction`` (forward/backward)."""
        self.unified_layer_svc.copy_boxes_to_adjacent_frame_by_direction(
            s_id, layer_name, item_keys, direction
        )

    # Used by AnnotationHandler
    def delete_boxes_by_keys_and_tab_id_for_current_frame_by_session_id(
            self, s_id: SessionId, box_keys: list[str], tab: VideoDataLayerGroup
    ):
        """Delete bounding boxes identified by ``keys`` from the current frame in the ``tab`` layer."""
        self.unified_layer_svc.delete_boxes_by_keys_and_tab_id_for_current_frame_by_session_id(
            s_id, box_keys, tab
        )

    def add_manual_boxes_to_current_frame(
            self,
            s_id: SessionId,
            tab: VideoDataLayerGroup,
            boxes: Iterable[tuple[str, BBoxXYXYTuple, str]],
    ) -> list[str]:
        """Add clipboard boxes as new manual boxes to the active editable layer."""
        return self.unified_layer_svc.add_manual_boxes_to_current_frame(s_id, tab, boxes)

    def replace_tab_frame_boxes(
            self,
            s_id: SessionId,
            tab: VideoDataLayerGroup,
            frame_index: int,
            boxes: list[BBoxViewModel],
    ) -> None:
        """Restore an editable tab frame from a mutation-history snapshot."""
        self.unified_layer_svc.replace_tab_frame_boxes(s_id, tab, frame_index, boxes)

    def get_tab_frame_boxes_at_frame_index(
            self, s_id: SessionId, tab: VideoDataLayerGroup, frame_index: int
    ) -> list[BBoxViewModel]:
        """Return cloned editable-tab boxes for an explicit frame."""
        return self.unified_layer_svc.get_tab_frame_boxes_at_frame_index(s_id, tab, frame_index)

    # Used by UIHandler
    def get_tab_frame_boxes_for_session_id(
            self, s_id: SessionId, tab: VideoDataLayerGroup
    ) -> FrameBoxesViewModel:
        """Retrieve all bounding boxes for the current frame in the specified ``tab`` layer."""
        return self.unified_layer_svc.get_tab_frame_boxes_for_session_id(s_id, tab)

    # Used by AnnotationHandler
    def get_layer_box_by_key(
            self, s_id: SessionId, layer_name: VideoDataLayer, key: str
    ) -> BBoxViewModel | None:
        """Fetch a single bounding detection by its unique ``key`` from ``layer_name``."""
        return self.unified_layer_svc.get_layer_box_by_key(s_id, layer_name, key)

    # Used by AnnotationHandler
    def reset_all_for_layer(self, s_id: SessionId, layer_name: VideoDataLayer) -> None:
        """Clear **all** bounding boxes in the specified ``layer_name`` for ``s_id``."""
        self.unified_layer_svc.reset_all_for_layer(s_id, layer_name)

    # Used by AnnotationHandler
    def reset_frame_for_layer(
            self, s_id: SessionId, layer_name: VideoDataLayer, frame_index: int
    ) -> None:
        """Clear all bounding boxes in the specified ``layer_name`` for the frame at ``frame_index``."""
        self.unified_layer_svc.reset_frame_for_layer(s_id, layer_name, frame_index)

    # Used by AnnotationHandler
    def delete_tracks_by_id_and_direction(
            self, s_id: SessionId, t_id: str, direction: Direction
    ):
        """Delete tracking occurrences in the specified ``direction`` (forward/backward) from track ``t_id``."""
        return self.tracking_layer_svc.delete_tracks_by_id_and_direction(
            s_id, t_id, direction
        )

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
    #                    DETECTION SERVICE DELEGATION METHODS
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

    # Used by DetectionHandler
    def detect_current_frame(self, s_id: SessionId) -> None:
        """Run detection on the current frame of ``s_id`` using the active detection model."""
        self.detection_svc.detect_current_frame_and_populate_layer_b_at_current_index(s_id)

    # Used by ModelHandler
    def get_selected_detection_model_name(self, s_id: SessionId) -> str:
        """Retrieve the name of the currently selected detection model for ``s_id``."""
        return self.get_session_by_id(s_id).state.settings.detection_model_name

    # Used by ModelLoadWorker
    def set_detection_model(
            self, s_id: SessionId, model_name: str, keep_manual: bool
    ) -> None:
        """Switch the detection model for ``s_id`` and optionally preserve manual annotations."""
        self.detection_svc.set_detection_model_for_session_id(
            s_id, model_name, keep_manual
        )

    # Used by DetectionHandler
    def start_detection_worker(self, s_id: SessionId) -> None:
        """Start a background ``DetectionWorker`` to process all frames in ``s_id``."""
        self.detection_svc.start_detection_worker_for_session_id(s_id)

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
    #                     TRACKING SERVICE DELEGATION METHODS
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

    # Used by TrackingHandler
    def start_tracking_worker(
            self, s_id: SessionId, strategy: str, source: VideoDataLayer
    ) -> None:
        """Start a background ``TrackingWorker`` using the specified ``strategy`` on ``source`` detections."""
        self.tracking_svc.start_background_tracking(s_id, strategy, source)

    # Used by TrackingHandler
    def sync_tracking_cache(self, s_id: SessionId) -> None:
        """Synchronize the tracking cache with the current view_state for ``s_id``."""
        self.tracking_svc.sync_tracking_cache(s_id)

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
    #                      EXPORT SERVICE DELEGATION METHODS
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

    # Used by ExportAllWorker
    def export_session(
            self,
            s_id: SessionId,
            output_path: str,
            progress_callback: Callable[[int, int], None] | None = None,
    ) -> None:
        """
        Export the session ``s_id`` to a blurred video and metadata files at ``output_path``.
        
        Optionally, provide a ``progress_callback`` that will be invoked as ``(frames_processed, total_frames)``.
        """
        self.export_svc.export_session(s_id, output_path, progress_callback)

    # Used by ExportHandler
    def session_is_ready_for_export(self, s_id: SessionId) -> bool:
        """Check if the session ``s_id`` has valid tracking data and is ready to export."""
        return self.export_svc.session_is_ready_for_export(s_id)

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
    #                      SESSION SERVICE DELEGATION METHODS
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

    # Used by SessionHandler
    def open_videos(self, paths: Iterable[str]) -> list[str]:
        """Create new ``Session`` instances from video files at the given ``paths``."""
        return self.session_svc.open_videos(paths)

    # Used by PlaybackHandler
    def session_has_buffered_frame(self, s_id: SessionId) -> bool:
        """Check if a pre-decoded frame is available in the buffer for ``s_id``."""
        return self.session_svc.session_by_id_has_buffered_frame(s_id)

    def session_has_running_detection_worker(self, s_id: SessionId) -> bool:
        """Check if a ``DetectionWorker`` is actively running for ``s_id``."""
        return self.session_svc.session_by_id_has_running_detection_worker(s_id)

    # Used by TrackingHandler
    def session_has_running_tracking_worker(self, s_id: SessionId) -> bool:
        """Check if a ``TrackingWorker`` is actively running for ``s_id``."""
        return self.session_svc.session_by_id_has_running_tracking_worker(s_id)

    def handle_active_session_changed(
            self, old_s_id: SessionId | None, new_s_id: SessionId
    ):
        """Notify services that the active session has changed from ``old_s_id`` to ``new_s_id``."""
        self.session_svc.handle_active_session_changed(
            old_s_id=old_s_id, new_s_id=new_s_id
        )

    # Used by PlaybackHandler
    def start_session_playback(self, s_id: SessionId) -> None:
        """Initialize and start playback for the session ``s_id``."""
        # [TODO] Delegate to a dedicated playback service or expand SessionService
        self.session_svc.start_session_playback(s_id=s_id)

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
    #               LAYER IMPORT / EXPORT DELEGATION METHODS
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

    # Used by ImportExportHandler
    def import_layer(
        self,
        s_id: SessionId,
        layer: VideoDataLayer | str,
        file_path: str,
        mode: services.ImportMode | str,
    ) -> int:
        """
        Import bounding-box data from ``file_path`` into ``layer`` for ``s_id``.

        Dispatches to :class:`DetectionImportService` for layers A/B and
        :class:`TrackingImportService` for layers C/D.

        Args:
            s_id:      Target session.
            layer:     Target layer (as enum or string; coerced to enum).
            file_path: Path to import file.
            mode:      Merge strategy (enum or string; coerced to enum).

        Returns:
            int: Number of boxes written into the layer.

        Note:
            Accepts string layer names to handle Qt signal/slot type coercion.
        """
        layer = ensure_layer_enum(layer)
        mode = ensure_import_mode(mode)
        from app.domain.video.layer import VideoDataLayer as _L
        if layer in (_L.A, _L.B):
            return self.detection_import_svc.import_layer(s_id, layer, file_path, mode)
        return self.tracking_import_svc.import_layer(s_id, layer, file_path, mode)

    # Used by ImportExportHandler
    def export_layer(
        self,
        s_id: SessionId,
        layer: VideoDataLayer | str,
        file_path: str,
    ) -> int:
        """
        Export bounding-box data from ``layer`` for ``s_id`` to ``file_path``.

        Dispatches to :class:`DetectionExportService` for layers A/B and
        :class:`TrackingExportService` for layers C/D.

        Args:
            s_id:      Source session.
            layer:     Source layer (as enum or string; coerced to enum).
            file_path: Destination path.

        Returns:
            int: Number of boxes written to the file.

        Note:
            Accepts string layer names to handle Qt signal/slot type coercion.
        """
        layer = ensure_layer_enum(layer)
        from app.domain.video.layer import VideoDataLayer as _L
        if layer in (_L.A, _L.B):
            return self.detection_export_svc.export_layer(s_id, layer, file_path)
        return self.tracking_export_svc.export_layer(s_id, layer, file_path)
