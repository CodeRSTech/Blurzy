# Feedback widgets

Source: `src/app/ui/qt/widgets/feedback/`

This package contains reusable feedback controls such as the spinner label
used to communicate busy or waiting states.

`InlineSpinnerLabel` is a small reusable feedback widget for displaying
activity alongside the control or operation that owns the busy state. The
widget presents status; handlers and worker progress signals determine when
that status is shown or cleared.

See [UI handlers](../../handlers.md) for progress orchestration and
[Qt sections](../sections.md) for the panels that host shared widgets.
