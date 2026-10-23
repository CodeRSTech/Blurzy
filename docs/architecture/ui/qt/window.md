# Main window

Source: `src/app/ui/qt/window`

`Window` builds the main Qt window, places the preview, side panels, transport
controls, and data panel, and exposes UI events to the controller/handlers.
Close handling coordinates the UI shutdown path; session and worker cleanup
are performed through Application/session lifecycle operations rather than by
individual child widgets.

See [Qt sections](sections.md), [preview widgets](widgets.md), and
[UI handlers](../handlers.md) for the components the window composes.
