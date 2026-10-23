# Project domain

Source: `src/app/domain/project`

`ProjectDocument` is the versioned top-level save/restore value. It groups
project directories and session documents; each session document records the
video path, frame position, settings, next annotation identifier, and layer
data needed by the project workflow. These are data structures rather than
file operations.

The [project store](../infrastructure/project.md) serializes and validates
these documents, while the [project service](../application/services/index.md)
reopens videos and restores live sessions. Per-session runtime state is
described in [Session](session.md).
