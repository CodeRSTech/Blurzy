"""
Application Layer
=================

The Application Layer is responsible for orchestrating the workflow of the application.
It coordinates actions across domain objects and infrastructure services,
deciding what should happen in response to user actions.
This layer exposes operations that the UI can call,
without depending on concrete widget behavior or layout details.

It has managers, such as the

``DetectionEngineManager``,
which centralizes logic for creating, updating, and removing detection engines on a per-session basis.

``SessionManager`` which handles the lifecycle of sessions, including creation, selection, and deletion.

``SessionInitializer`` which is responsible for initializing sessions with the necessary collaborators and resources.

``TrackingWorkerManager`` which manages the lifecycle of tracking workers for sessions.

``VideoDecodeWorkerManager`` which manages the lifecycle of video decode workers for sessions.
Purpose
-------
Implements app use-cases and workflow orchestration.

Examples:

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

- **Talks upward to:** UI layer through returned data/results
- **Talks downward to:** Domain layer and Infrastructure layer
- **Must not depend on:** concrete widget behavior or layout details
"""

# from .editor_app_service import EditorAppService

# __all__ = ["EditorAppService"]
