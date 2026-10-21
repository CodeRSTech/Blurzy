"""Video infrastructure — PyAV reader with rotation support, background decode worker with ring buffer.

Layer: Infrastructure.
Context: Implements concrete processing and I/O behind application-facing contracts.
"""

from .reader import VideoReader
from .decode_worker import VideoDecodeWorker

__all__ = ["VideoDecodeWorker", "VideoReader"]