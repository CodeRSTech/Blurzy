# Video domain

Source: `src/app/domain/video`

This package defines immutable video metadata, mutable playback position and
status, navigation direction, the four annotation-layer identifiers and their
UI groups, and a bounded ring buffer for sequential frame access. These types
describe state and data boundaries; opening files and decoding frames are
infrastructure responsibilities.

Session state combines playback and metadata with other per-video values
([Session](session.md)). The runtime reader and decode worker are in
[video infrastructure](../infrastructure/video.md); the layers are used by
[detection](detection.md) and [tracking](tracking.md) workflows.
