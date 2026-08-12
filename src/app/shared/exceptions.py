from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QListWidget
    from app.domain.session import SessionId


class BlurzyException(Exception):
    """Base exception for domain/business failures in Blurzy."""


class DomainException(BlurzyException):
    """Domain/application boundary error."""


class InfrastructureException(BlurzyException):
    """Infrastructure/runtime integration error."""


class SessionAlreadyExistsException(DomainException):
    def __init__(self, message: str, full_path: str) -> None:
        super().__init__(f"{message}\n"
                         f"Session already exists for path: '{full_path}'")
        self.full_path = full_path


class NoNewOpenedSessionsException(DomainException):
    def __init__(self, num_open_sessions: int) -> None:
        super().__init__(
            f"No new sessions opened. Number of open sessions: {num_open_sessions}"
        )
        self.num_open_sessions = num_open_sessions


class NoItemsInSessionListException(DomainException):
    def __init__(self, session_list: QListWidget) -> None:
        super().__init__("No items in session list.")
        self.session_list = session_list


class UnsupportedLayerException(DomainException):
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
    def __init__(self, message: str, session_id: SessionId) -> None:
        super().__init__(
            f"{message}\n"
            f"Tracking already in progress for {session_id}"
        )
        self.session_id = session_id


class EmptyLayerException(DomainException):
    def __init__(self, message: str, layer_name: str, session_id: SessionId) -> None:
        super().__init__(
            f"{message}\n"
            f"Layer '{layer_name}' is empty. "
            f"Session ID: '{session_id}'"
        )
        self.layer_name = layer_name
        self.session_id = session_id


class InvalidSessionIdException(DomainException):
    def __init__(self, message: str, session_id: SessionId | None) -> None:
        super().__init__(
            f"{message}\n"
            f"Invalid session ID: '{session_id}'"
        )
        self.session_id = session_id


class TrackingWorkerNotFoundException(DomainException):
    def __init__(self, message: str, session_id: SessionId) -> None:
        super().__init__(
            f"{message}\n"
            f"Tracking worker not found for Session ID: '{session_id}'"
        )
        self.session_id = session_id


class WorkerAlreadyRunningException(DomainException):
    def __init__(self, message: str, session_id: SessionId) -> None:
        super().__init__(
            f"{message}\n"
            f"Detection already in progress for Session ID: '{session_id}'"
        )
        self.session_id = session_id


class NullModelNameException(DomainException):
    def __init__(self, message: str, session_id: SessionId) -> None:
        super().__init__(
            f"{message}\n"
            f"Model name is null or empty for Session ID: '{session_id}'"
        )
        self.session_id = session_id


class VideoFileOpenException(InfrastructureException):
    def __init__(self, path: str, reason: str) -> None:
        super().__init__(f"Unable to open/read video file '{path}'. {reason}")
        self.path = path


class VideoStreamStateException(InfrastructureException):
    def __init__(self, path: str, detail: str) -> None:
        super().__init__(f"Invalid video stream state for '{path}': {detail}")
        self.path = path


class VideoReadFrameException(InfrastructureException):
    def __init__(self, path: str, frame_index: int, reason: str) -> None:
        super().__init__(f"Failed to read frame {frame_index} from '{path}': {reason}")
        self.path = path
        self.frame_index = frame_index


class EndOfVideoStreamException(InfrastructureException):
    def __init__(self, path: str) -> None:
        super().__init__(f"End of stream reached for: {path}")
        self.path = path


class UnsupportedLayerOperationException(DomainException):
    def __init__(self, operation: str, layer_name: object) -> None:
        super().__init__(f"Unsupported layer for operation '{operation}': {layer_name}")
        self.operation = operation
        self.layer_name = layer_name


class ImmutableLayerOperationException(DomainException):
    def __init__(self, operation: str, layer_name: object) -> None:
        super().__init__(f"Cannot perform '{operation}' on immutable layer: {layer_name}")
        self.operation = operation
        self.layer_name = layer_name


class UnsupportedDirectionException(DomainException):
    def __init__(self, direction: object) -> None:
        super().__init__(f"Unsupported direction: {direction}")
        self.direction = direction


class UnsupportedTabException(DomainException):
    def __init__(self, tab: object) -> None:
        super().__init__(f"Unsupported tab name: {tab}")
        self.tab = tab


class UnknownFrameItemException(DomainException):
    def __init__(self, item_key: str) -> None:
        super().__init__(f"Unknown frame item: {item_key}")
        self.item_key = item_key


class UnsupportedImportExportFormatException(DomainException):
    def __init__(self, extension: str, operation: str) -> None:
        super().__init__(
            f"Unsupported file extension '{extension}' for {operation}. Expected '.json' or '.csv'."
        )
        self.extension = extension
        self.operation = operation


class ProjectFormatException(DomainException):
    def __init__(self, detail: str) -> None:
        super().__init__(f"Invalid project file: {detail}")
        self.detail = detail


class MissingProjectAssetException(DomainException):
    def __init__(self, missing_paths: list[str]) -> None:
        formatted = "\n".join(f"- {path}" for path in missing_paths)
        super().__init__(
            "Project file references missing video files:\n"
            f"{formatted}"
        )
        self.missing_paths = missing_paths