# Session infrastructure

Source: `src/app/infrastructure/session/`

`Session` is the runtime container around a video, domain `SessionState`, and
the four-layer `SessionDataStore`. `SessionInitializer` attaches the reader,
decode worker, and state when a video opens; closing a session stops its
detection, tracking, and decode workers and closes the reader. The data store
uses a reentrant lock for its layer operations and offers snapshots and
machine-box replacement that retains manual annotations. `SessionFrameAccessor`
provides frame retrieval through the session's reader/buffer boundary.

Project payload conversion is supported by the store, but file persistence is
owned by [ProjectStore](project.md). See [Session domain](../domain/session.md),
[Application managers](../application/managers.md), and [video infrastructure](video.md).
