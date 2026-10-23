# Qt dialogs

Source: `src/app/ui/qt/dialogs`

Dialogs collect or confirm choices for annotation edits, labels, preferences,
import/export, model changes, and multi-session export. They own form controls
and local validation/presentation; handlers decide when to open them and pass
the accepted values to Application workflows. The dialogs do not execute
video processing themselves.

See [UI handlers](../handlers.md) for orchestration,
[Qt sections](sections.md) for dialog-adjacent panels, and
[Qt workers](workers.md) for asynchronous model loading.
