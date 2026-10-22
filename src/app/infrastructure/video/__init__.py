"""Video infrastructure — PyAV reader with rotation support, background decode worker with ring buffer.

See Also:
    - [`VideoReader`][app.infrastructure.video.reader.VideoReader] — reads video streams
    - [`VideoDecodeWorker`][app.infrastructure.video.decode_worker.VideoDecodeWorker] — decodes frames for playback

Layer: Infrastructure.
Context: Implements concrete processing and I/O behind application-facing contracts.
"""

from .reader import VideoReader
from .decode_worker import VideoDecodeWorker

__all__ = ["VideoDecodeWorker", "VideoReader"]