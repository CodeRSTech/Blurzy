"""
Application Layer
=================

The Application Layer is responsible for orchestrating the workflow of the application.
It coordinates actions across domain objects and infrastructure services,
deciding what should happen in response to user actions.
This layer exposes operations that the UI can call,
without depending on concrete widget behavior or layout details.

It has managers, such as the

[`DetectionEngineManager`][app.application.managers.detection_engine.DetectionEngineManager] - centralizes logic for creating, updating, and removing detection engines on a per-session basis.

[`SessionManager`][app.application.managers.session.SessionManager] - handles the lifecycle of sessions, including creation, selection, and deletion.

[`SessionInitializer`][app.application.managers.session_initializer.SessionInitializer] - responsible for initializing sessions with the necessary collaborators and resources.

[`TrackingWorkerManager`][app.application.managers.tracking_worker.TrackingWorkerManager] - manages the lifecycle of tracking workers for sessions.

[`VideoDecodeWorkerManager`][app.application.managers.video_decode_worker.VideoDecodeWorkerManager] - manages the lifecycle of video decode workers for sessions.

See Also:
    - [`Application`][app.application.application.Application] — exposes orchestrated workflows to the UI
    - [`SessionService`][app.application.services.session_service.SessionService] — coordinates session and worker use cases

Purpose
-------
Implements app use-cases and workflow orchestration.

???+ example "Example usage"

    - open videos
    - create sessions
    - select active session
    - load frame
    - move to next/previous frame
    - later: play, pause, seek, export

Responsibilities
----------------

- coordinate actions across domain objects and infrastructure services
- decide what should happen for a user action
- expose operations the UI can call

Communication
-------------

- **Talks upward to:** [UI layer][app.ui] through returned data/results
- **Talks downward to:** [Domain layer][app.domain] and [Infrastructure layer][app.infrastructure] through method calls and data manipulation
- **Must not depend on:** concrete widget behavior or layout details


    Layer: Application.
    Context: Coordinates application workflows.
    """

# from .editor_app_service import EditorAppService

# __all__ = ["EditorAppService"]
