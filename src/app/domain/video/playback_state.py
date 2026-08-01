"""Playback state management — frame position and playback status."""

from dataclasses import dataclass
from typing import override


@dataclass(slots=True)
class PlaybackState:
    """
    Tracks the current playback state of a video session.

    Attributes:
        _current_frame_index (int): Currently displayed frame as a 0-based index.
        _is_playing (bool): Whether the video is actively playing.

    Note:
        Uses property accessors with private backing fields while still keeping
        a lightweight slotted dataclass layout. Instances start at frame 0 with
        playback paused, then update as the user plays, pauses, or seeks.
        Supports tracking the visible frame, controlling playback, updating UI
        progress indicators, and synchronizing buffered data with user position.
    """
    _current_frame_index: int = 0
    _is_playing: bool = False

    @property
    def current_frame_index(self) -> int:
        return self._current_frame_index

    @current_frame_index.setter
    def current_frame_index(self, value: int) -> None:
        self._current_frame_index = value

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    @is_playing.setter
    def is_playing(self, value: bool) -> None:
        self._is_playing = value

    @override
    def __repr__(self) -> str:
        return f"PlaybackState(current_frame_index={self.current_frame_index}, is_playing={self.is_playing})"

    @override
    def __str__(self) -> str:
        return f"PlaybackState: Frame {self.current_frame_index}, Playing: {self.is_playing}"

    def stop_playback(self) -> None:
        self._is_playing = False