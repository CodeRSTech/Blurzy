# Video interfaces

Source: `src/app/application/interfaces/video/`

`VideoDecodeWorkerControlInterface` exposes the small control surface needed
by the video-decode manager: activate or deactivate a worker, stop it cleanly,
and retrieve a cached frame when available. The manager uses this contract to
prioritize the active session without taking a direct dependency on the
concrete decoder implementation.

Frame decoding and buffering are owned by [video infrastructure](../../infrastructure/video.md);
session-level coordination is in [managers](../managers.md). The interface
does not itself promise that a requested frame is already buffered.
