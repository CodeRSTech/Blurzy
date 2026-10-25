"""
Module for exceptions; provides reusable helpers across application layers.

See Also:
    - [`SessionManager`][app.application.managers.session.SessionManager] — raises session lifecycle exceptions
    - [`SessionHandler`][app.ui.handlers.session_handler.SessionHandler] — handles session-opening failures in the UI

Layer: Shared utilities.
Context: Provides reusable helpers across application layers at this architectural boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QListWidget
    from app.domain.session import SessionId


class BlurzyException(Exception):
    """
    Base exception for domain/business failures in Blurzy.

    Layer: Shared utilities.
    Context: Provides reusable cross-layer behavior without owning workflow state.
    """


class DomainException(BlurzyException):
    """
    Domain/application boundary error.

    Layer: Shared utilities.
    Context: Provides reusable cross-layer behavior without owning workflow state.
    """


class InfrastructureException(BlurzyException):
    """
    Infrastructure/runtime integration error.

    Layer: Shared utilities.
    Context: Provides reusable cross-layer behavior without owning workflow state.
    """


class SessionAlreadyExistsException(DomainException):
    """
    Signal the session already exists error condition.


    Args:
        message: Message describing the error or condition.
        full_path: Full path of the video file.
    """
    def __init__(self, message: str, full_path: str) -> None:
        super().__init__(f"{message}\n"
                         f"Session already exists for path: '{full_path}'")
        self.full_path = full_path


class NoNewOpenedSessionsException(DomainException):
    """
    Signal the no new opened sessions error condition.


    Args:
        num_open_sessions: Number of sessions that were already open.
    """
    def __init__(self, num_open_sessions: int) -> None:
        super().__init__(
            f"No new sessions opened. Number of open sessions: {num_open_sessions}"
        )
        self.num_open_sessions = num_open_sessions


class NoItemsInSessionListException(DomainException):
    """
    Signal the no items in session list error condition.


    Args:
        session_list: Session entries available to the operation.
    """
    def __init__(self, session_list: QListWidget) -> None:
        super().__init__("No items in session list.")
        self.session_list = session_list


class UnsupportedLayerException(DomainException):
    """
    Signal the unsupported layer error condition.


    Args:
        message: Message describing the error or condition.
        source_layer_name: Name of the source layer.
        session_id: Identifier of the session associated with this object.
    """
    def __init__(
        self, message: str, source_layer_name: str, session_id: SessionId
    ) -> None:
        super().__init__(
            f"{message}\n"
            f"Found unsupported layer name: {source_layer_name}. "
            f"Session ID: '{session_id}'"
        )
        self.source_layer_name = source_layer_name
        self.session_id = session_id


class TrackingWorkerAlreadyRunningException(DomainException):
    """
    Signal the tracking worker already running error condition.


    Args:
        message: Message describing the error or condition.
        session_id: Identifier of the session associated with this object.
    """
    def __init__(self, message: str, session_id: SessionId) -> None:
        super().__init__(
            f"{message}\n"
            f"Tracking already in progress for {session_id}"
        )
        self.session_id = session_id


class EmptyLayerException(DomainException):
    """
    Signal the empty layer error condition.


    Args:
        message: Message describing the error or condition.
        layer_name: Name of the affected layer.
        session_id: Identifier of the session associated with this object.
    """
    def __init__(self, message: str, layer_name: str, session_id: SessionId) -> None:
        super().__init__(
            f"{message}\n"
            f"Layer '{layer_name}' is empty. "
            f"Session ID: '{session_id}'"
        )
        self.layer_name = layer_name
        self.session_id = session_id


class InvalidSessionIdException(DomainException):
    """
    Signal the invalid session id error condition.


    Args:
        message: Message describing the error or condition.
        session_id: Identifier of the session associated with this object.
    """
    def __init__(self, message: str, session_id: SessionId | None) -> None:
        super().__init__(
            f"{message}\n"
            f"Invalid session ID: '{session_id}'"
        )
        self.session_id = session_id


class TrackingWorkerNotFoundException(DomainException):
    """
    Signal the tracking worker not found error condition.


    Args:
        message: Message describing the error or condition.
        session_id: Identifier of the session associated with this object.
    """
    def __init__(self, message: str, session_id: SessionId) -> None:
        super().__init__(
            f"{message}\n"
            f"Tracking worker not found for Session ID: '{session_id}'"
        )
        self.session_id = session_id


class WorkerAlreadyRunningException(DomainException):
    """
    Signal the worker already running error condition.


    Args:
        message: Message describing the error or condition.
        session_id: Identifier of the session associated with this object.
    """
    def __init__(self, message: str, session_id: SessionId) -> None:
        super().__init__(
            f"{message}\n"
            f"Detection already in progress for Session ID: '{session_id}'"
        )
        self.session_id = session_id


class NullModelNameException(DomainException):
    """
    Signal the null model name error condition.


    Args:
        message: Message describing the error or condition.
        session_id: Identifier of the session associated with this object.
    """
    def __init__(self, message: str, session_id: SessionId) -> None:
        super().__init__(
            f"{message}\n"
            f"Model name is null or empty for Session ID: '{session_id}'"
        )
        self.session_id = session_id


class VideoFileOpenException(InfrastructureException):
    """
    Signal the video file open error condition.


    Args:
        path: Filesystem path of the video or resource.
        reason: Explanation of why the operation failed.
    """
    def __init__(self, path: str, reason: str) -> None:
        super().__init__(f"Unable to open/read video file '{path}'. {reason}")
        self.path = path


class VideoStreamStateException(InfrastructureException):
    """
    Signal the video stream state error condition.


    Args:
        path: Filesystem path of the video or resource.
        detail: Details describing the invalid state or operation.
    """
    def __init__(self, path: str, detail: str) -> None:
        super().__init__(f"Invalid video stream state for '{path}': {detail}")
        self.path = path


class VideoReadFrameException(InfrastructureException):
    """
    Signal the video read frame error condition.


    Args:
        path: Filesystem path of the video or resource.
        frame_index: Zero-based video frame associated with the error.
        reason: Explanation of why the operation failed.
    """
    def __init__(self, path: str, frame_index: int, reason: str) -> None:
        super().__init__(f"Failed to read frame {frame_index} from '{path}': {reason}")
        self.path = path
        self.frame_index = frame_index


class EndOfVideoStreamException(InfrastructureException):
    """
    Signal the end of video stream error condition.


    Args:
        path: Filesystem path of the video or resource.
    """
    def __init__(self, path: str) -> None:
        super().__init__(f"End of stream reached for: {path}")
        self.path = path


class UnsupportedLayerOperationException(DomainException):
    """
    Signal the unsupported layer operation error condition.


    Args:
        operation: Name of the attempted operation.
        layer_name: Name of the affected layer.
    """
    def __init__(self, operation: str, layer_name: object) -> None:
        super().__init__(f"Unsupported layer for operation '{operation}': {layer_name}")
        self.operation = operation
        self.layer_name = layer_name


class ImmutableLayerOperationException(DomainException):
    """
    Signal the immutable layer operation error condition.


    Args:
        operation: Name of the attempted operation.
        layer_name: Name of the affected layer.
    """
    def __init__(self, operation: str, layer_name: object) -> None:
        super().__init__(f"Cannot perform '{operation}' on immutable layer: {layer_name}")
        self.operation = operation
        self.layer_name = layer_name


class UnsupportedDirectionException(DomainException):
    """
    Signal the unsupported direction error condition.


    Args:
        direction: Frame-navigation direction.
    """
    def __init__(self, direction: object) -> None:
        super().__init__(f"Unsupported direction: {direction}")
        self.direction = direction


class UnsupportedTabException(DomainException):
    """
    Signal the unsupported tab error condition.


    Args:
        tab: Tab identifier associated with the request.
    """
    def __init__(self, tab: object) -> None:
        super().__init__(f"Unsupported tab name: {tab}")
        self.tab = tab


class UnknownFrameItemException(DomainException):
    """
    Signal the unknown frame item error condition.


    Args:
        item_key: Key identifying the frame item.
    """
    def __init__(self, item_key: str) -> None:
        super().__init__(f"Unknown frame item: {item_key}")
        self.item_key = item_key


class UnsupportedImportExportFormatException(DomainException):
    """
    Signal the unsupported import export format error condition.


    Args:
        extension: File extension that was supplied.
        operation: Name of the attempted operation.
    """
    def __init__(self, extension: str, operation: str) -> None:
        super().__init__(
            f"Unsupported file extension '{extension}' for {operation}. Expected '.json' or '.csv'."
        )
        self.extension = extension
        self.operation = operation


class ProjectFormatException(DomainException):
    """
    Signal the project format error condition.


    Args:
        detail: Details describing the invalid state or operation.
    """
    def __init__(self, detail: str) -> None:
        super().__init__(f"Invalid project file: {detail}")
        self.detail = detail
