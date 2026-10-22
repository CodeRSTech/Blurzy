# Domain view models

Source: `src/app/domain/views/`

These plain data models shape information for presentation without being Qt
widgets. They include a box row with source and tracking metadata, a
per-frame box collection, model-selector choices, session-file entries, and
formatted session settings. `ViewModelService` and infrastructure view-model
helpers assemble these values from session/domain data for UI consumers.

Interactive selection and undo history are separate [UI view state](../ui/view_state.md).
Detection and tracking result values remain in [their domain packages](detection.md);
see [infrastructure view models](../infrastructure/views.md) for adapters.
