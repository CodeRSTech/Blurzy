# Session domain

Source: `src/app/domain/session`

`SessionId` identifies an open video session. `SessionState` holds its domain
metadata, playback position/status, processing settings, current-frame data,
and annotation identifier state; it does not own a decoder, worker, or
annotation store. The Application session manager and initializer assemble
those runtime collaborators around the state.

See [video values](video.md), [session infrastructure](../infrastructure/session.md),
and [Application managers](../application/managers.md) for runtime ownership
and lifecycle.
