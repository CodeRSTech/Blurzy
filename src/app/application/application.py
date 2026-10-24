"""
Module for application; coordinates application workflows.

See Also:
    - [`SessionManager`][app.application.managers.session.SessionManager] — owns session lifecycle operations
    - [`DetectionService`][app.application.services.detection.service.DetectionService] — coordinates detection workflows

Layer: Application.
Context: Coordinates application workflows at this architectural boundary.
"""

from __future__ import annotations

from typing import final, override, TYPE_CHECKING

from PySide6.QtCore import QObject

from app.application.managers import SessionManager
from app.application import services
from app.application.services.helpers.layer_coercion import ensure_import_mode, ensure_layer_enum

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from typing import Unpack
    from app.application.services.project_service import ProjectLoadReport
    from app.domain.project import ProjectDirectories, ProjectDocument
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
        - Manages the `SessionManager` for session lifecycle and view_state tracking.

    Note:
        Design pattern:
            This class acts as a Façade — every method is a direct pass-through to a service.
            No logic should live here; all decisions belong in services.
            The UI Controller imports and calls only this class (not individual services).


    Layer: Application.
    Context: Coordinates use-case behavior through domain services and application contracts.
    """

    def __init__(self) -> None:
        """
        Initialize the application with all service instances.
        """
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
        self.project_svc = services.ProjectService(self)
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
        """
        Return a concise string representation of the Application instance.

        Returns:
            str: The string representation.
        """
        return "Application()"

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
    #                            PROPERTIES
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

    @property
    def active_session(self) -> Session | None:
        """
        Retrieve the currently active session instance.

        Returns:
            Session | None: The active session, or None if no session is active.
        """
        return self.sm.active_session

    @property
    def active_session_id(self) -> SessionId | None:
        """
        Retrieve the identifier of the currently active session.

        Returns:
            SessionId | None: The ID of the active session, or None if none is active.
        """
        return self.sm.active_session_id

    @active_session_id.setter
    def active_session_id(self, s_id: SessionId) -> None:
        """
        Set the active session by its identifier.

        Args:
            s_id (SessionId): The session identifier to mark as active.
        """
        self.sm.active_session_id = s_id

    @property
    def all_s_ids(self) -> Iterable[SessionId]:
        """
        Iterate over all session identifiers currently managed by the application.

        Returns:
            Iterable[SessionId]: A collection of all active session IDs.
        """
        return self.sm.all_session_ids

    @property
    def current_project_path(self) -> str:
        """
        Retrieve the file path of the currently active project.

        Returns:
            str: The absolute or relative file path of the current project.
        """
        return self.project_svc.current_project_path

    @property
    def project_directories(self) -> ProjectDirectories:
        """
        Retrieve the directories associated with the current project.

        Returns:
            ProjectDirectories: The directory structure and paths for the active project.
        """
        return self.project_svc.directories

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
    #                       SESSION MANAGER DELEGATION METHODS
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

    # Used by UIController
    def close(self) -> None:
        """
        Close all active sessions and shut down the SessionManager.
        """
        self.sm.close_all()

    def clear_project(self) -> None:
        """
        Clear the currently active project from memory.
        """
        self.project_svc.clear_project()

    def save_project(self, file_path: str) -> ProjectDocument:
        """
        Save the current project to the specified file path.

        Args:
            file_path (str): The destination file path to save the project.

        Returns:
            ProjectDocument: The document representation of the saved project.
        """
        return self.project_svc.save_project(file_path)

    def load_project(self, file_path: str) -> ProjectLoadReport:
        """
        Load a project from the specified file path.

        Args:
            file_path (str): The file path of the project to load.

        Returns:
            `ProjectLoadReport` with the restored-session count and video paths
            skipped because their sessions could not be restored.
        """
        return self.project_svc.load_project(file_path)

    def update_project_directories(
            self,
            *,
            last_import_directory: str | None = None,
            last_export_directory: str | None = None,
            export_prefix: str | None = None,
            export_suffix: str | None = None,
    ) -> None:
        """
        Update the directories and naming conventions associated with the current project.

        Args:
            last_import_directory (str | None, optional): The path of the last used import directory. Defaults to None.
            last_export_directory (str | None, optional): The path of the last used export directory. Defaults to None.
            export_prefix (str | None, optional): The default prefix for exported files. Defaults to None.
            export_suffix (str | None, optional): The default suffix for exported files. Defaults to None.
        """
        self.project_svc.update_directories(
            last_import_directory=last_import_directory,
            last_export_directory=last_export_directory,
            export_prefix=export_prefix,
            export_suffix=export_suffix,
        )

    # Used by SessionService
    def open_video_from_path(self, path: str) -> None:
        """
        Open a video file and create a new session from the provided path.

        Args:
            path (str): The file path to the video.
        """
        self.sm.create_session_from_video_path(path)

    # Used by SessionService
    def initialize_active_session(self) -> None:
        """
        Set the first available session as the active session.
        """
        self.sm.initialize_active_session()

    # Used by SessionHandler
    def get_session_settings(self, s_id: SessionId) -> SessionSettingsViewModel:
        """
        Retrieve the SessionSettingsViewModel for the specified session.

        Note:
            `ProcessingSettings` and `SessionSettingsViewModel` intentionally differ:
                - `ProcessingSettings.chosen_labels` -> `list[str]`
                - `SessionSettingsViewModel.chosen_labels` -> `str` (comma-separated, UI-ready)
            These are converted via `ProcessingSettings.as_view_model()`.

        Args:
            s_id (SessionId): The target session identifier.

        Returns:
            SessionSettingsViewModel: The settings view model for the session.
        """
        return self.sm.get_session_by_id(s_id).state.settings.as_view_model()

    # Used by PlaybackHandler
    def get_session_frame_interval_ms(self, s_id: SessionId) -> int:
        """
        Calculate and return the frame interval in milliseconds for the specified session.

        Args:
            s_id (SessionId): The target session identifier.

        Returns:
            int: The calculated interval between frames in milliseconds.
        """
        return self.sm.get_session_state_by_id(
            s_id
        ).metadata.calculate_interval_in_mas()

    # Used by AnnotationHandler, DetectionHandler, UIHandler etc.
    def get_session_by_id(self, s_id: SessionId) -> Session:
        """
        Fetch the Session instance identified by the given session ID.

        Delegates to the `SessionManager` to retrieve the session. It is recommended
        to use this method rather than calling the SessionManager directly.

        Args:
            s_id (SessionId): The identifier of the session to fetch.

        Returns:
            Session: The requested session instance.

        Raises:
            KeyError: If the session with the specified ID does not exist.
        """
        return self.sm.get_session_by_id(s_id)

    # Used by PlaybackHandler
    def is_at_last_frame(self, s_id: SessionId) -> bool:
        """
        Check if the playback position for the session is at the final frame.

        Args:
            s_id (SessionId): The target session identifier.

        Returns:
            bool: True if playback is at the last frame, False otherwise.
        """
        return self.sm.get_session_state_by_id(s_id).is_at_last_frame

    # Used by PlaybackHandler
    def is_session_playing(self, s_id: SessionId) -> bool:
        """
        Check if the specified session is currently playing.

        Args:
            s_id (SessionId): The target session identifier.

        Returns:
            bool: True if the session is currently playing, False otherwise.
        """
        return self.sm.get_session_state_by_id(s_id).playback.is_playing

    # Used by PlaybackHandler
    def load_frame_by_index(self, s_id: SessionId, frame_index: int) -> RGBFrame | None:
        """
        Load a specific frame by its index for the specified session.

        Args:
            s_id (SessionId): The target session identifier.
            frame_index (int): The index of the frame to load.

        Returns:
            RGBFrame | None: The requested frame, or None if unavailable.
        """
        self.sm.get_frame_for_session_id_by_index(frame_index, s_id)

    # Used by PlaybackHandler
    def load_next_frame(self, s_id: SessionId) -> RGBFrame | None:
        """
        Advance to and load the next frame in the specified session.

        Args:
            s_id (SessionId): The target session identifier.

        Returns:
            RGBFrame | None: The next frame, or None if unavailable.
        """
        self.sm.get_next_frame_for_session_id(s_id)

    # Used by PlaybackHandler (only usage so far)
    def load_previous_frame(self, s_id: SessionId) -> RGBFrame | None:
        """
        Rewind to and load the previous frame in the specified session.

        Args:
            s_id (SessionId): The target session identifier.

        Returns:
            RGBFrame | None: The previous frame, or None if unavailable.
        """
        self.sm.get_previous_frame_for_session_id(s_id)

    def set_session_state_is_playing(self, s_id: SessionId, is_playing: bool) -> None:
        """
        Set the playback state (playing/paused) for the specified session.

        Args:
            s_id (SessionId): The target session identifier.
            is_playing (bool): True to set state to playing, False for paused.
        """
        self.sm.get_session_state_by_id(s_id).playback.is_playing = is_playing

    # Used by PlaybackHandler and SessionHandler
    def stop_all_playback(self) -> None:
        """
        Stop playback for all active sessions.
        """
        self.sm.stop_all_playback()

    # Used by DetectionHandler, ExportHandler, ModelHandler, and TrackingHandler
    def update_session_settings(
            self, s_id: SessionId, **kwargs: Unpack[ProcessingSettingsKwargs]
    ) -> None:
        """
        Update processing settings for the specified session.

        Args:
            s_id (SessionId): The target session identifier.
            **kwargs (Unpack[ProcessingSettingsKwargs]): Keyword arguments corresponding to processing settings to update.
        """
        self.session_svc.update_session_settings(s_id, **kwargs)

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
    #                   DETECTION LAYER SERVICE DELEGATION METHODS
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

    # Used by DetectionHandler
    def apply_filters_to_layer(self, layer_name: VideoDataLayer, s_id: SessionId) -> None:
        """
        Apply confidence and size filters to the specified layer.

        Operates on `DataLayer.B` (reviewed detections) or `DataLayer.D` (reviewed tracks)
        for the given session ID.

        Args:
            layer_name (VideoDataLayer): The layer to apply filters to.
            s_id (SessionId): The target session identifier.
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
        """
        Add a manually drawn bounding detection box to Layer B for the current frame.

        Args:
            s_id (SessionId): The target session identifier.
            label (str): The classification label for the box.
            bbox_xyxy (BBoxXYXYTuple): The coordinates of the bounding box.
            color_hex (str, optional): The hex color string for the box. Defaults to "#00ff00".
        """
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
        """
        Update a bounding detection's label and coordinates in the specified layer at the current frame.

        Args:
            s_id (SessionId): The target session identifier.
            layer_name (VideoDataLayer): The data layer where the box resides.
            box_key (str): The unique identifier for the bounding box.
            label (str): The updated classification label.
            bbox_xyxy (BBoxXYXYTuple): The updated coordinates for the bounding box.
        """
        self.unified_layer_svc.update_current_frame_box_xyxy(s_id, layer_name, box_key, label, bbox_xyxy)

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
    #               UNIFIED LAYER SERVICE DELEGATION METHODS
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

    # Used by AnnotationHandler
    def change_current_layer_boxes_by_keys_and_dxdy(self, s_id: SessionId, layer_name: VideoDataLayer,
                                                    box_keys: Iterable[str], dx: int, dy: int) -> int:
        """
        Translate bounding boxes in the specified layer by dx and dy pixels.

        Args:
            s_id (SessionId): The target session identifier.
            layer_name (VideoDataLayer): The layer containing the boxes.
            box_keys (Iterable[str]): A collection of unique identifiers for the boxes to move.
            dx (int): The translation distance along the x-axis.
            dy (int): The translation distance along the y-axis.

        Returns:
            int: The count of bounding boxes successfully moved.
        """
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
        """
        Duplicate bounding boxes to the adjacent frame in the specified direction.

        Args:
            s_id (SessionId): The target session identifier.
            layer_name (VideoDataLayer): The layer containing the boxes.
            item_keys (Iterable[str]): The unique identifiers for the boxes to duplicate.
            direction (Direction): The direction (forward or backward) of the adjacent frame.
        """
        self.unified_layer_svc.copy_boxes_to_adjacent_frame_by_direction(
            s_id, layer_name, item_keys, direction
        )

    # Used by AnnotationHandler
    def delete_boxes_by_keys_and_tab_id_for_current_frame_by_session_id(
            self, s_id: SessionId, box_keys: list[str], tab: VideoDataLayerGroup
    ):
        """
        Delete specific bounding boxes from the current frame in the designated tab layer.

        Args:
            s_id (SessionId): The target session identifier.
            box_keys (list[str]): The unique identifiers of the boxes to delete.
            tab (VideoDataLayerGroup): The tab layer grouping where the boxes reside.
        """
        self.unified_layer_svc.delete_boxes_by_keys_and_tab_id_for_current_frame_by_session_id(
            s_id, box_keys, tab
        )

    def add_manual_boxes_to_current_frame(
            self,
            s_id: SessionId,
            tab: VideoDataLayerGroup,
            boxes: Iterable[tuple[str, BBoxXYXYTuple, str]],
    ) -> list[str]:
        """
        Add clipboard boxes as new manual boxes to the active editable layer.

        Args:
            s_id (SessionId): The target session identifier.
            tab (VideoDataLayerGroup): The tab layer grouping.
            boxes (Iterable[tuple[str, BBoxXYXYTuple, str]]): An iterable of box data tuples
                containing (label, coordinates, color).

        Returns:
            list[str]: A list of assigned keys for the newly created boxes.
        """
        return self.unified_layer_svc.add_manual_boxes_to_current_frame(s_id, tab, boxes)

    def replace_tab_frame_boxes(
            self,
            s_id: SessionId,
            tab: VideoDataLayerGroup,
            frame_index: int,
            boxes: list[BBoxViewModel],
    ) -> None:
        """
        Restore an editable tab frame from a mutation-history snapshot.

        Args:
            s_id (SessionId): The target session identifier.
            tab (VideoDataLayerGroup): The target tab layer group.
            frame_index (int): The index of the frame to restore.
            boxes (list[BBoxViewModel]): The list of view models representing the restored boxes.
        """
        self.unified_layer_svc.replace_tab_frame_boxes(s_id, tab, frame_index, boxes)

    def get_tab_frame_boxes_at_frame_index(
            self, s_id: SessionId, tab: VideoDataLayerGroup, frame_index: int
    ) -> list[BBoxViewModel]:
        """
        Return cloned editable-tab boxes for an explicit frame.

        Args:
            s_id (SessionId): The target session identifier.
            tab (VideoDataLayerGroup): The target tab layer group.
            frame_index (int): The target frame index.

        Returns:
            list[BBoxViewModel]: A list of view models representing the boxes on the specified frame.
        """
        return self.unified_layer_svc.get_tab_frame_boxes_at_frame_index(s_id, tab, frame_index)

    # Used by UIHandler
    def get_tab_frame_boxes_for_session_id(
            self, s_id: SessionId, tab: VideoDataLayerGroup
    ) -> FrameBoxesViewModel:
        """
        Retrieve all bounding boxes for the current frame in the specified tab layer.

        Args:
            s_id (SessionId): The target session identifier.
            tab (VideoDataLayerGroup): The target tab layer group.

        Returns:
            FrameBoxesViewModel: A view model containing all bounding boxes for the frame.
        """
        return self.unified_layer_svc.get_tab_frame_boxes_for_session_id(s_id, tab)

    # Used by AnnotationHandler
    def get_layer_box_by_key(
            self, s_id: SessionId, layer_name: VideoDataLayer, key: str
    ) -> BBoxViewModel | None:
        """
        Fetch a single bounding detection by its unique key from the specified layer.

        Args:
            s_id (SessionId): The target session identifier.
            layer_name (VideoDataLayer): The data layer to query.
            key (str): The unique identifier of the bounding box.

        Returns:
            BBoxViewModel | None: The view model for the requested box, or None if not found.
        """
        return self.unified_layer_svc.get_layer_box_by_key(s_id, layer_name, key)

    # Used by AnnotationHandler
    def reset_all_for_layer(self, s_id: SessionId, layer_name: VideoDataLayer) -> None:
        """
        Clear all bounding boxes entirely in the specified layer for the session.

        Args:
            s_id (SessionId): The target session identifier.
            layer_name (VideoDataLayer): The layer to be cleared.
        """
        self.unified_layer_svc.reset_all_for_layer(s_id, layer_name)

    # Used by AnnotationHandler
    def reset_frame_for_layer(
            self, s_id: SessionId, layer_name: VideoDataLayer, frame_index: int
    ) -> None:
        """
        Clear all bounding boxes in the specified layer for a specific frame index.

        Args:
            s_id (SessionId): The target session identifier.
            layer_name (VideoDataLayer): The layer to be cleared.
            frame_index (int): The index of the frame to clear.
        """
        self.unified_layer_svc.reset_frame_for_layer(s_id, layer_name, frame_index)

    # Used by AnnotationHandler
    def delete_tracks_by_id_and_direction(
            self, s_id: SessionId, t_id: str, direction: Direction
    ):
        """
        Delete tracking occurrences in the specified direction from a specific track.

        Args:
            s_id (SessionId): The target session identifier.
            t_id (str): The unique identifier of the track to truncate/delete.
            direction (Direction): The direction (forward/backward) in which to delete.
        """
        return self.tracking_layer_svc.delete_tracks_by_id_and_direction(
            s_id, t_id, direction
        )

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
    #                    DETECTION SERVICE DELEGATION METHODS
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

    # Used by DetectionHandler
    def detect_current_frame(self, s_id: SessionId) -> None:
        """
        Run detection on the current frame using the active detection model.

        Args:
            s_id (SessionId): The target session identifier.
        """
        self.detection_svc.detect_current_frame_and_populate_layer_b_at_current_index(s_id)

    # Used by ModelHandler
    def get_selected_detection_model_name(self, s_id: SessionId) -> str:
        """
        Retrieve the name of the currently selected detection model for the session.

        Args:
            s_id (SessionId): The target session identifier.

        Returns:
            str: The name of the active detection model.
        """
        return self.get_session_by_id(s_id).state.settings.detection_model_name

    # Used by ModelLoadWorker
    def set_detection_model(
            self, s_id: SessionId, model_name: str, keep_manual: bool
    ) -> None:
        """
        Switch the detection model for the session, optionally preserving manual annotations.

        Args:
            s_id (SessionId): The target session identifier.
            model_name (str): The name of the new detection model to load.
            keep_manual (bool): Flag indicating whether manually added annotations should be preserved.
        """
        self.detection_svc.set_detection_model_for_session_id(
            s_id, model_name, keep_manual
        )

    # Used by DetectionHandler
    def start_detection_worker(self, s_id: SessionId) -> None:
        """
        Start a background DetectionWorker to process all frames in the session.

        Args:
            s_id (SessionId): The target session identifier.
        """
        self.detection_svc.start_detection_worker_for_session_id(s_id)

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
    #                     TRACKING SERVICE DELEGATION METHODS
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

    # Used by TrackingHandler
    def start_tracking_worker(
            self, s_id: SessionId, strategy: str, source: VideoDataLayer
    ) -> None:
        """
        Start a background TrackingWorker using the specified strategy and source layer.

        Args:
            s_id (SessionId): The target session identifier.
            strategy (str): The specific tracking algorithm strategy to utilize.
            source (VideoDataLayer): The data layer containing the source detections.
        """
        self.tracking_svc.start_background_tracking(s_id, strategy, source)

    # Used by TrackingHandler
    def sync_tracking_cache(self, s_id: SessionId) -> None:
        """
        Synchronize the tracking cache with the current view_state for the session.

        Args:
            s_id (SessionId): The target session identifier.
        """
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
        Export the session to a blurred video and metadata files at the given path.

        Args:
            s_id (SessionId): The target session identifier.
            output_path (str): The file path where the output should be written.
            progress_callback (Callable[[int, int], None] | None, optional):
                A callback invoked as (frames_processed, total_frames). Defaults to None.
        """
        self.export_svc.export_session(s_id, output_path, progress_callback)

    # Used by ExportHandler
    def session_is_ready_for_export(self, s_id: SessionId) -> bool:
        """
        Check if the session has valid tracking data and is ready for export.

        Args:
            s_id (SessionId): The target session identifier.

        Returns:
            bool: True if the session is ready for export, False otherwise.
        """
        return self.export_svc.session_is_ready_for_export(s_id)

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
    #                      SESSION SERVICE DELEGATION METHODS
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

    # Used by SessionHandler
    def open_videos(self, paths: Iterable[str]) -> list[str]:
        """
        Create new Session instances from video files at the provided paths.

        Args:
            paths (Iterable[str]): An iterable of file paths to video files.

        Returns:
            list[str]: A list of the newly created session identifiers.
        """
        return self.session_svc.open_videos(paths)

    # Used by PlaybackHandler
    def session_has_buffered_frame(self, s_id: SessionId) -> bool:
        """
        Check if a pre-decoded frame is currently available in the buffer for the session.

        Args:
            s_id (SessionId): The target session identifier.

        Returns:
            bool: True if a buffered frame is available, False otherwise.
        """
        return self.session_svc.session_by_id_has_buffered_frame(s_id)

    def session_has_running_detection_worker(self, s_id: SessionId) -> bool:
        """
        Check if a DetectionWorker is actively running for the session.

        Args:
            s_id (SessionId): The target session identifier.

        Returns:
            bool: True if a detection worker is running, False otherwise.
        """
        return self.session_svc.session_by_id_has_running_detection_worker(s_id)

    # Used by TrackingHandler
    def session_has_running_tracking_worker(self, s_id: SessionId) -> bool:
        """
        Check if a TrackingWorker is actively running for the session.

        Args:
            s_id (SessionId): The target session identifier.

        Returns:
            bool: True if a tracking worker is running, False otherwise.
        """
        return self.session_svc.session_by_id_has_running_tracking_worker(s_id)

    def handle_active_session_changed(
            self, old_s_id: SessionId | None, new_s_id: SessionId
    ):
        """
        Notify services that the active session has changed.

        Args:
            old_s_id (SessionId | None): The previously active session identifier.
            new_s_id (SessionId): The newly active session identifier.
        """
        self.session_svc.handle_active_session_changed(
            old_s_id=old_s_id, new_s_id=new_s_id
        )

    # Used by PlaybackHandler
    def start_session_playback(self, s_id: SessionId) -> None:
        """
        Initialize and start playback for the specified session.

        Args:
            s_id (SessionId): The target session identifier.
        """
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
        Import bounding-box data from a file into a specified layer.

        Dispatches to `DetectionImportService` for layers A/B and
        `TrackingImportService` for layers C/D.

        Note:
            Accepts string layer names to handle Qt signal/slot type coercion.

        Args:
            s_id (SessionId): The target session identifier.
            layer (VideoDataLayer | str): Target layer (as enum or string; coerced to enum).
            file_path (str): Absolute or relative path to the import file.
            mode (services.ImportMode | str): Merge strategy (enum or string; coerced to enum).

        Returns:
            int: Number of bounding boxes successfully written into the layer.
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
        Export bounding-box data from a specified layer to a file.

        Dispatches to `DetectionExportService` for layers A/B and
        `TrackingExportService` for layers C/D.

        Note:
            Accepts string layer names to handle Qt signal/slot type coercion.

        Args:
            s_id (SessionId): The source session identifier.
            layer (VideoDataLayer | str): Source layer (as enum or string; coerced to enum).
            file_path (str): Destination file path for the export.

        Returns:
            int: Number of bounding boxes successfully written to the file.
        """
        layer = ensure_layer_enum(layer)
        from app.domain.video.layer import VideoDataLayer as _L
        if layer in (_L.A, _L.B):
            return self.detection_export_svc.export_layer(s_id, layer, file_path)
        return self.tracking_export_svc.export_layer(s_id, layer, file_path)