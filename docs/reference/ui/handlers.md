# UI handlers

Source: `src/app/ui/handlers/`

Handlers translate window and widget actions into calls on the UI application
adapter. Separate handlers coordinate sessions, playback, annotation edits,
detection, tracking, projects, preferences, dialogs, and export/import. They
connect workflow signals to progress and error presentation and request
preview/table refreshes; session rules and processing decisions remain in
Application services.

The handlers share presentation state from [UI view state](view_state.md) and
communicate through [UI interfaces and adapters](interfaces.md). Concrete
dialogs, preview widgets, and the [main window](qt/window.md) provide the user
interaction surface.
