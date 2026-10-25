# Session domain

Source: `src/app/domain/session`

`SessionId` gives each opened video a stable session key. `SessionState` is the
domain snapshot that describes that session: source metadata, playback
position/status, processing settings, current-frame data, and the next
annotation identity. It contains values and behavior for session state, not
resources such as an open decoder, Qt worker, or layer database.

That distinction matters during save/load. Project documents serialize the
session's paths, settings, frame position, annotation data, and identifier
state; opening a project must recreate runtime resources rather than serialize
live Qt or video objects. See [Project domain](project.md) and
[Project persistence](../infrastructure/project.md).

At runtime, the Application manager composes a `SessionState` with an
infrastructure `Session`, reader, decode worker, and four-layer store. See
[session infrastructure](../infrastructure/session.md) for ownership and
[video values](video.md) for playback and metadata types.
