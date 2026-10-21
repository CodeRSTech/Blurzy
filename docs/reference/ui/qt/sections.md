# Qt sections

Source: `src/app/ui/qt/sections/`

The sections package composes the major window regions: the right-side
controls, bottom data panel, and transport controls. The main window owns the
overall layout and places these sections around the preview; handlers connect
their user actions to application workflows and refreshes.

See [Main window](window.md), [preview and custom widgets](widgets.md), and
[UI handlers](../handlers.md). Section widgets present state; they do not own
session or worker lifecycle.
