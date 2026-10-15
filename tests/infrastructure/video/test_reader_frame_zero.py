from __future__ import annotations

import numpy as np

from app.infrastructure.video.reader import VideoReader


class _FakeFrame:
    def __init__(self, value: int) -> None:
        self.value = value

    def to_ndarray(self, format: str) -> np.ndarray:
        assert format == "rgb24"
        return np.full((2, 3, 3), self.value, dtype=np.uint8)


class _FakeContainer:
    def __init__(self) -> None:
        self.frames = [_FakeFrame(10), _FakeFrame(20)]

    def decode(self, stream):
        return iter(self.frames)


def _reader() -> VideoReader:
    reader = VideoReader.__new__(VideoReader)
    reader._container = _FakeContainer()
    reader._stream = object()
    reader._frame_iter = None
    reader._current_index = 0
    reader._base_rotation = 0
    reader._manual_rotation = 0
    return reader


def test_first_sequential_read_returns_actual_frame_zero():
    reader = _reader()

    actual_index, frame = reader.read_next_frame()

    assert actual_index == 0
    assert np.all(frame == 10)


def test_indexed_read_of_frame_zero_decodes_the_first_video_frame():
    reader = _reader()

    frame = reader.read_frame_at_index(0)

    assert frame is not None
    assert np.all(frame == 10)
