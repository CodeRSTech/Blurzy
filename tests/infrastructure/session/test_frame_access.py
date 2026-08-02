"""Unit tests for SessionFrameAccessor polling/seek behavior."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from app.infrastructure.session.frame_access import SessionFrameAccessor


class _PlaybackStub:
    def __init__(self, current_frame_index: int) -> None:
        self.current_frame_index = current_frame_index


class _MetadataStub:
    def __init__(self, frame_count: int) -> None:
        self.frame_count = frame_count


class _StateStub:
    def __init__(self, *, frame_count: int, current_index: int) -> None:
        self.metadata = _MetadataStub(frame_count=frame_count)
        self.playback = _PlaybackStub(current_frame_index=current_index)
        self.current_frame_data = None
        self.updated = None

    def update_current_frame_data_and_index(self, idx: int, frame_data) -> None:
        self.playback.current_frame_index = idx
        self.current_frame_data = frame_data
        self.updated = (idx, frame_data)


def test_constructor_validates_timeout_and_poll_interval():
    """Accessor should reject invalid timeout and poll values up front."""
    with pytest.raises(ValueError, match="timeout_seconds must be > 0"):
        SessionFrameAccessor(timeout_seconds=0)

    with pytest.raises(ValueError, match="poll_interval_seconds must be > 0"):
        SessionFrameAccessor(poll_interval_seconds=0)


def test_cached_hit_updates_state_without_seeking():
    """A cache hit should update playback state and skip seek/polling."""
    accessor = SessionFrameAccessor(timeout_seconds=0.05, poll_interval_seconds=0.01)
    state = _StateStub(frame_count=10, current_index=2)
    worker = MagicMock(name="decode_worker")
    worker.get_cached_frame_at_index.return_value = "frame-4"

    result = accessor.get_frame_by_index(
        session_state=cast(Any, state),
        decode_worker=worker,
        frame_index=4,
    )

    assert result == "frame-4"
    assert state.playback.current_frame_index == 4
    assert state.current_frame_data == "frame-4"
    worker.request_seek.assert_not_called()


def test_non_sequential_miss_seeks_and_recovers_frame():
    """Large jumps should request seek and then update state once frame appears."""
    accessor = SessionFrameAccessor(timeout_seconds=0.05, poll_interval_seconds=0.01)
    state = _StateStub(frame_count=20, current_index=1)
    worker = MagicMock(name="decode_worker")

    responses = iter([None, None, "frame-19"])

    def _cache_lookup(_idx: int):
        return next(responses, None)

    worker.get_cached_frame_at_index.side_effect = _cache_lookup

    with patch("app.infrastructure.session.frame_access.time.sleep", return_value=None):
        result = accessor.get_frame_by_index(
            session_state=cast(Any, state),
            decode_worker=worker,
            frame_index=999,
        )

    assert result == "frame-19"
    worker.request_seek.assert_called_once_with(19)
    assert state.updated == (19, "frame-19")


def test_sequential_miss_times_out_without_seek():
    """Sequential underruns should not seek; they should timeout cleanly if still missing."""
    accessor = SessionFrameAccessor(timeout_seconds=0.02, poll_interval_seconds=0.01)
    state = _StateStub(frame_count=8, current_index=3)
    worker = MagicMock(name="decode_worker")
    worker.get_cached_frame_at_index.return_value = None

    with patch("app.infrastructure.session.frame_access.time.sleep", return_value=None):
        result = accessor.get_frame_by_index(
            session_state=cast(Any, state),
            decode_worker=worker,
            frame_index=4,
        )

    assert result is None
    worker.request_seek.assert_not_called()
    assert state.current_frame_data is None


