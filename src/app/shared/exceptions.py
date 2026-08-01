from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QListWidget
    from app.domain.session import SessionId


class SessionAlreadyExistsException(Exception):
    def __init__(self, message:str, full_path: str) -> None:
        super().__init__(f"{message}\n"
                         f"Session already exists for path: '{full_path}'")
        self.full_path = full_path


class NoNewOpenedSessionsException(Exception):
    def __init__(self, num_open_sessions: int) -> None:
        super().__init__(
            f"No new sessions opened. Number of open sessions: {num_open_sessions}"
        )
        self.num_open_sessions = num_open_sessions


class NoItemsInSessionListException(Exception):
    def __init__(self, session_list: QListWidget) -> None:
        super().__init__("No items in session list.")
        self.session_list = session_list


class UnsupportedLayerException(Exception):
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


class TrackingWorkerAlreadyRunningException(Exception):
    def __init__(self, message: str, session_id: SessionId) -> None:
        super().__init__(
            f"{message}\n"
            f"Tracking already in progress for {session_id}"
        )
        self.session_id = session_id


class EmptyLayerException(Exception):
    def __init__(self, message: str, layer_name: str, session_id: SessionId) -> None:
        super().__init__(
            f"{message}\n"
            f"Layer '{layer_name}' is empty. "
            f"Session ID: '{session_id}'"
        )
        self.layer_name = layer_name
        self.session_id = session_id


class InvalidSessionIdException(Exception):
    def __init__(self, message: str, session_id: SessionId | None) -> None:
        super().__init__(
            f"{message}\n"
            f"Invalid session ID: '{session_id}'"
        )
        self.session_id = session_id


class TrackingWorkerNotFoundException(Exception):
    def __init__(self, message: str, session_id: SessionId) -> None:
        super().__init__(
            f"{message}\n"
            f"Tracking worker not found for Session ID: '{session_id}'"
        )
        self.session_id = session_id


class WorkerAlreadyRunningException(Exception):
    def __init__(self, message: str, session_id: SessionId) -> None:
        super().__init__(
            f"{message}\n"
            f"Detection already in progress for Session ID: '{session_id}'"
        )
        self.session_id = session_id

class NullModelNameException(Exception):
    def __init__(self, message: str, session_id: SessionId) -> None:
        super().__init__(
            f"{message}\n"
            f"Model name is null or empty for Session ID: '{session_id}'"
        )
        self.session_id = session_id