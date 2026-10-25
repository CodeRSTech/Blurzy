# Qt sections

Source: `src/app/ui/qt/sections`

The sections package composes the major window regions: the right-side
controls, bottom data panel, and transport controls. The main window owns the
overall layout and places these sections around the preview; handlers connect
their user actions to application workflows and refreshes.

See [Main window](window.md), [preview and custom widgets](widgets.md), and
[UI handlers](../handlers.md). Section widgets present state; they do not own
session or worker lifecycle.

The right control panel groups detection, tracking, privacy, preview, and
render settings into collapsible sections. The application theme is selected
in Settings and can follow the system palette or use the explicit light/dark
palettes. Primary detection, tracking, and export actions are visually
emphasized without changing their behavior.

The bottom data tables render each annotation's color as a compact swatch;
the exact color value remains available as a tooltip and accessible text.
