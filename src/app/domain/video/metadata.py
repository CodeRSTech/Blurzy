"""Video file metadata — dimensions, FPS, frame count, and timing."""

from dataclasses import dataclass
from typing import override


@dataclass(slots=True)
class VideoMetadata:
    """
    Static information about a video file (immutable after creation).

    Attributes:
        _path (str): File path to the video file.
        _width (int): Video resolution width in pixels.
        _height (int): Video resolution height in pixels.
        _fps (float): Frames per second for playback.
        _frame_count (int): Total number of frames in the video.

    Note:
        Extracted once when a video opens, typically from ``VideoReader``.
        Used to validate frame indices, calculate playback timing, and display
        resolution, FPS, and frame count in the UI. Immutable after creation.

    Example:
        metadata = VideoMetadata(
            path="/home/user/video.mp4",
            width=1920,
            height=1080,
            fps=30.0,
            frame_count=900  # 30 seconds at 30 fps
        )

        interval_ms = metadata.calculate_interval_in_mas()  # 33ms (30fps)
        max_idx = metadata.frame_count - 1  # 899
        safe_idx = min(requested_idx, max_idx)  # Clamp to valid range
    """
    _path: str
    _width: int
    _height: int
    _fps: float
    _frame_count: int

    @override
    def __str__(self) -> str:
        return f"VideoMetadata(path={self._path}, width={self._width}, height={self._height}, fps={self._fps}, frame_count={self._frame_count})"

    @property
    def path(self) -> str:
        return self._path

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def frame_count(self) -> int:
        return self._frame_count

    def calculate_interval_in_mas(self):
        fps = self.fps if self.fps > 1e-6 else 30.0
        return max(1, int(round(1000.0 / fps)))