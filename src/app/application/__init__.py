"""
Application Layer
=================

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
