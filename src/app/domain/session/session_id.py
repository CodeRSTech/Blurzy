"""Session identifier — unique key for a video processing session."""

import os
from dataclasses import dataclass
from typing import final, override


@final
@dataclass(frozen=True)
class SessionId:
    """
    Unique identifier for a video processing session.

    Attributes:
        path (str): Absolute file path to the video file.

    Note:
        Immutable and hashable so it can safely serve as a stable dictionary
        key or set member. Equality is value-based on the stored path, making
        it suitable for identifying sessions in function parameters, UI display,
        and internal lookups without risk of accidental mutation.

    Example:
        s_id = SessionId(path="/home/user/video.mp4")
        print(s_id.basename)  # "video.mp4"
        print(s_id.basename_without_extension)  # "video"
    """
    path: str

    def __bool__(self) -> bool:
        """Returns False if the path is empty, True otherwise."""
        return bool(self.path and self.path.strip())

    @override
    def __str__(self) -> str:
        """Returns the session id as a string."""
        return self.basename

    @override
    def __eq__(self, other: object) -> bool:
        """Allows comparison with other FileID objects or raw strings."""
        if isinstance(other, SessionId):
            return self.path == other.path
        if isinstance(other, str):
            return self.path == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.path)

    @property
    def basename(self):
        return os.path.basename(self.path)

    @property
    def basename_without_extension(self):
        return os.path.splitext(self.basename)[0]