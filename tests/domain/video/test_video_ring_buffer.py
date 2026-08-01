from __future__ import annotations

from app.domain.video.ring_buffer import VideoRingBuffer


class TestVideoRingBuffer:
    def test_get_returns_none_when_empty(self):
        rb = VideoRingBuffer(capacity=3)
        assert rb.get(0) is None

    def test_push_and_get_roundtrip(self):
        rb = VideoRingBuffer(capacity=3)
        rb.push(10, "f10")
        rb.push(11, "f11")

        assert rb.get(10) == "f10"
        assert rb.get(11) == "f11"

    def test_wrap_drops_oldest_index(self):
        rb = VideoRingBuffer(capacity=3)
        rb.push(1, "f1")
        rb.push(2, "f2")
        rb.push(3, "f3")
        rb.push(4, "f4")

        assert rb.get(1) is None
        assert rb.get(2) == "f2"
        assert rb.get(3) == "f3"
        assert rb.get(4) == "f4"

    def test_clear_resets_cached_frames(self):
        rb = VideoRingBuffer(capacity=3)
        rb.push(5, "f5")
        rb.clear()

        assert rb.get(5) is None
