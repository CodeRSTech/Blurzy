# Session interfaces

Source: `src/app/application/interfaces/session/`

`SessionDataStoreInterface` abstracts CRUD and bulk operations on a session's
four annotation layers. It covers frame-level and whole-layer reads/writes,
filtering, clearing, and replacing machine-generated boxes while retaining
manual boxes. It is a live session-data contract, not the project-file
persistence API.

The concrete store and its ownership are documented in
[session infrastructure](../../infrastructure/session.md); project JSON is
handled separately by [project persistence](../../infrastructure/project.md).
Services access layer data through the active session.
