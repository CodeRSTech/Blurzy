import os
from pathlib import Path

import pytest
from app.domain.video.playback_state import PlaybackState
from app.infrastructure.video.decode_worker import VideoDecodeWorker

TEST_VIDEO_PATH = os.getenv("BLURZY_TEST_VIDEO_PATH", "").strip()


def _wait_worker_running(qtbot, worker: VideoDecodeWorker) -> None:
    qtbot.waitUntil(worker.isRunning, timeout=2000)


def _max_frame_index(worker: VideoDecodeWorker) -> int:
    return max(0, worker._reader.frame_count - 1)


def _target_or_skip(worker: VideoDecodeWorker, preferred: int, *, min_required: int) -> int:
    max_idx = _max_frame_index(worker)
    if max_idx < min_required:
        pytest.skip(
            f"Video too short for this integration scenario: max_idx={max_idx}, "
            f"required>={min_required}"
        )
    return min(preferred, max_idx)


def _target_with_tail_or_skip(
    worker: VideoDecodeWorker, preferred: int, *, min_required: int, tail_frames: int
) -> int:
    max_idx = _max_frame_index(worker)
    if max_idx < min_required:
        pytest.skip(
            f"Video too short for this integration scenario: max_idx={max_idx}, "
            f"required>={min_required}"
        )
    latest_safe_start = max_idx - tail_frames
    if latest_safe_start < 0:
        pytest.skip(
            f"Video too short for contiguous tail validation: max_idx={max_idx}, "
            f"tail_frames={tail_frames}"
        )
    return min(preferred, latest_safe_start)


@pytest.fixture
def worker_setup(qtbot):
    """
    A Pytest fixture that safely sets up and tears down the worker for every test.
    This prevents QThread memory leaks and dangling C++ objects!
    """
    if not TEST_VIDEO_PATH:
        pytest.skip("Set BLURZY_TEST_VIDEO_PATH to run integration worker tests.")
    if not Path(TEST_VIDEO_PATH).exists():
        pytest.skip(f"BLURZY_TEST_VIDEO_PATH does not exist: {TEST_VIDEO_PATH}")

    playback = PlaybackState()
    worker = VideoDecodeWorker(TEST_VIDEO_PATH, playback)

    yield worker, playback

    worker.stop()
    worker.wait(1000)


def test_hard_seek(qtbot, worker_setup):
    worker, playback = worker_setup
    worker.start()
    _wait_worker_running(qtbot, worker)

    # ACT & WAIT: Initialize the worker at frame 0
    with qtbot.waitSignal(worker.signals.seek_completed, timeout=5000):
        worker.set_active(True, resume_idx=0)

    # Testing a deep hard seek into the video
    target_frame = _target_or_skip(worker, 150, min_required=20)

    # ACT: Force a hard seek
    with qtbot.waitSignal(worker.signals.seek_completed, timeout=8000) as blocker:
        worker.request_seek(target_frame)

    # ASSERT: Check that the signal payload matches our requested frame
    assert blocker.args[0] == target_frame

    # ASSERT: The frame must now exist instantly in the O(1) cache
    cached_frame = worker.get_cached_frame_at_index(target_frame)
    assert cached_frame is not None
    assert cached_frame.shape[2] == 3


def test_cache_bounds_forward_and_backward(qtbot, worker_setup):
    worker, playback = worker_setup
    worker.start()
    _wait_worker_running(qtbot, worker)

    start_idx = _target_or_skip(worker, 200, min_required=60)
    probe_idx = min(start_idx + 40, _max_frame_index(worker))

    # FIX 1: Update the simulated UI playhead BEFORE we wake the worker
    playback.current_frame_index = start_idx

    # ACT: Wake the worker up and tell it to start buffering deep at Frame 200
    with qtbot.waitSignal(worker.signals.seek_completed, timeout=8000):
        worker.set_active(True, resume_idx=start_idx)

    # WAIT: The worker reads sequentially from 200 onwards.
    # FIX 2: We poll until Frame 240 is buffered.
    # (Since the throttle limit is ui_idx + 45, it will stop buffering at 245).
    def wait_for_buffer_to_fill():
        assert worker.get_cached_frame_at_index(probe_idx) is not None

    qtbot.waitUntil(wait_for_buffer_to_fill, timeout=8000)

    # ASSERT: Seek forward by a few frames (Cache Hit)
    assert worker.get_cached_frame_at_index(min(start_idx + 30, probe_idx)) is not None

    # ASSERT: Seek backward by a few frames (Cache Hit within the 90-frame window)
    assert worker.get_cached_frame_at_index(min(start_idx + 10, probe_idx)) is not None
    assert worker.get_cached_frame_at_index(start_idx) is not None

def test_play_and_pause_buffer_management(qtbot, worker_setup):
    worker, playback = worker_setup
    worker.start()
    _wait_worker_running(qtbot, worker)

    # Leave room for +4 contiguous-frame assertions below.
    start_frame = _target_with_tail_or_skip(
        worker, 500, min_required=10, tail_frames=4
    )

    # ACT: Simulate "Play" starting at frame 500
    with qtbot.waitSignal(worker.signals.seek_completed, timeout=10000):
        worker.set_active(True, resume_idx=start_frame)

    # Simulate the UI timer ticking every 16ms to pull 5 contiguous frames
    for i in range(start_frame, start_frame + 5):

        def wait_for_frame():
            assert worker.get_cached_frame_at_index(i) is not None

        qtbot.waitUntil(wait_for_frame, timeout=2000)
        # Update the playback view_state so the worker's throttle check (ui_idx + 45) stays happy
        playback.current_frame_index = i

        # ACT: Simulate "Pause"
    worker.set_active(False)

    # ASSERT: Buffer must be completely flushed to free memory
    assert worker.get_cached_frame_at_index(start_frame) is None
    assert worker.get_cached_frame_at_index(start_frame + 4) is None
