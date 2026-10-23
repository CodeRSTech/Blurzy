# UI view state

Source: `src/app/ui/view_state`

This package holds transient interaction state rather than persisted session
data: selected bounding boxes, preview tool mode, box-mutation/selection
history, and key filtering for the frame table. Annotation actions update the
active editable layer through Application workflows; the UI state tracks which
items and interactions are active, not the canonical box data.

The distinction matters when saving and restoring projects: domain settings,
playback, and layer contents belong to [session/project data](../domain/session.md),
while the window's current interaction belongs here. [Handlers](handlers.md)
coordinate these states with [preview widgets](qt/widgets.md).
