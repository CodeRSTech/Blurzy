# Video infrastructure

Source: `src/app/infrastructure/video`

`VideoReader` opens and decodes source media through PyAV, exposes metadata,
supports indexed and sequential frame reads, and applies detected plus
user-selected rotation. `VideoDecodeWorker` decodes ahead of playback into a
ring buffer, handles hard-seek requests, and can be activated or stopped by
the Application's per-session decode manager. The session uses buffered frames
for playback and falls back to reader access when needed.

The reader and worker are attached to a runtime [Session](session.md) during
initialization and closed during session teardown. Domain metadata and buffer
types are described in [Video domain](../domain/video.md).
