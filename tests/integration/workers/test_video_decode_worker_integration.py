import os
from pathlib import Path

import pytest
from app.domain.video.playback_state import PlaybackState
from app.infrastructure.video.decode_worker import VideoDecodeWorker

TEST_VIDEO_PATH = os.getenv("BLURZY_TEST_VIDEO_PATH", "").strip()


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

    # ACT & WAIT: Initialize the worker at frame 0
    with qtbot.waitSignal(worker.signals.seek_completed, timeout=2000):
        worker.set_active(True, resume_idx=0)

    # Testing a deep hard seek into the video
    target_frame = 150

    # ACT: Force a hard seek
    with qtbot.waitSignal(worker.signals.seek_completed, timeout=2000) as blocker:
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

    # FIX 1: Update the simulated UI playhead BEFORE we wake the worker
    playback.current_frame_index = 200

    # ACT: Wake the worker up and tell it to start buffering deep at Frame 200
    with qtbot.waitSignal(worker.signals.seek_completed, timeout=2000):
        worker.set_active(True, resume_idx=200)

    # WAIT: The worker reads sequentially from 200 onwards.
    # FIX 2: We poll until Frame 240 is buffered.
    # (Since the throttle limit is ui_idx + 45, it will stop buffering at 245).
    def wait_for_buffer_to_fill():
        assert worker.get_cached_frame_at_index(240) is not None

    qtbot.waitUntil(wait_for_buffer_to_fill, timeout=3000)

    # ASSERT: Seek forward by a few frames (Cache Hit)
    assert worker.get_cached_frame_at_index(230) is not None

    # ASSERT: Seek backward by a few frames (Cache Hit within the 90-frame window)
    assert worker.get_cached_frame_at_index(210) is not None
    assert worker.get_cached_frame_at_index(200) is not None

def test_play_and_pause_buffer_management(qtbot, worker_setup):
    worker, playback = worker_setup
    worker.start()

    start_frame = 500

    # ACT: Simulate "Play" starting at frame 500
    with qtbot.waitSignal(worker.signals.seek_completed, timeout=2000):
        worker.set_active(True, resume_idx=start_frame)

    # Simulate the UI timer ticking every 16ms to pull 5 contiguous frames
    for i in range(start_frame, start_frame + 5):

        def wait_for_frame():
            assert worker.get_cached_frame_at_index(i) is not None

        qtbot.waitUntil(wait_for_frame, timeout=500)
        # Update the playback state so the worker's throttle check (ui_idx + 45) stays happy
        playback.current_frame_index = i

        # ACT: Simulate "Pause"
    worker.set_active(False)

    # ASSERT: Buffer must be completely flushed to free memory
    assert worker.get_cached_frame_at_index(start_frame) is None
    assert worker.get_cached_frame_at_index(start_frame + 4) is None
