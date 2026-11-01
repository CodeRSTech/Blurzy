# Window, dialogs and preferences

Implementation: `src/app/ui/handlers/ui_handler.py`, `src/app/ui/handlers/dialogue_handler.py`, `src/app/ui/handlers/preferences_handler.py`

Three small handlers cover the presentation plumbing every workflow relies on:
`UIHandler` paints the current frame and its tables, `DialogueHandler` builds
dialogs that other handlers run, and `PreferencesHandler` stores user defaults.

## Where they sit

![UIHandler, DialogueHandler, and PreferencesHandler call the UIController, Application facade, SessionService, and SessionManager; preferences also use the shared preferences store](../../../assets/api/ui_handlers/sits_window-light.svg#only-light)
![UIHandler, DialogueHandler, and PreferencesHandler call the UIController, Application facade, SessionService, and SessionManager; preferences also use the shared preferences store](../../../assets/api/ui_handlers/sits_window-dark.svg#only-dark)

Arrows are calls. See the [big picture](../../big-picture.md) for the full
stack and the [handlers overview](../handlers.md) for the other handlers.

## The render pipeline

![Flow of render_saved_frame: read the frame, choose boxes, apply the preview overlay, paint, fill the table, then update labels and the slider](../../../assets/api/ui_handlers/render_pipeline-light.svg#only-light)
![Flow of render_saved_frame: read the frame, choose boxes, apply the preview overlay, paint, fill the table, then update labels and the slider](../../../assets/api/ui_handlers/render_pipeline-dark.svg#only-dark)

Almost every workflow ends by calling `UIController.render_frame_for_session_id`,
which delegates to `UIHandler.render_saved_frame`. It reads the session's current
frame index, frame count, and decoded frame; if there is no frame it returns
without redrawing. Otherwise it picks the boxes for the active data tab,
applies the **preview** overlay (preview settings affect only the editor, never
exported video), paints the frame, fills the table, and updates the frame label,
seek slider, and status bar.

!!! note "Preview is not export"

    Preview outlines, mask display, and live blur are editor settings. Render
    settings govern the exported video. See
    [export handlers](export-and-import.md).

## Dialogs

![Sequence in which a handler asks the controller for a dialog, the DialogueHandler builds it, and the caller runs it and reads the result](../../../assets/api/ui_handlers/dialogs_flow-light.svg#only-light)
![Sequence in which a handler asks the controller for a dialog, the DialogueHandler builds it, and the caller runs it and reads the result](../../../assets/api/ui_handlers/dialogs_flow-dark.svg#only-dark)

`DialogueHandler` **constructs but does not execute** dialogs. The calling
handler runs `exec()` and reads the answer, so the handler that knows the
workflow also decides what happens on accept or cancel.

!!! warning "Current behaviour"

    `LabelDialog` and `PreferencesDialog` are created directly by their
    handlers rather than through `DialogueHandler`, so the dialog factory is not
    the only construction path.

## Preferences

![Settings flow: open the dialog, then either reject with no change or save, apply theme and window preferences, and update the status text](../../../assets/api/ui_handlers/preferences_flow-light.svg#only-light)
![Settings flow: open the dialog, then either reject with no change or save, apply theme and window preferences, and update the status text](../../../assets/api/ui_handlers/preferences_flow-dark.svg#only-dark)

Preferences are **application defaults**, not live session settings. Accepting
the dialog saves them, applies the theme, refreshes icons, and applies window
preferences. A session picks the saved defaults up only when it is opened, via
`apply_defaults_to_session`.

## Worked example: saving preferences

![Sequence from Edit > Settings through the handler, dialog, store, and theme to the status text and a later video open](../../../assets/api/ui_handlers/preferences_example-light.svg#only-light)
![Sequence from Edit > Settings through the handler, dialog, store, and theme to the status text and a later video open](../../../assets/api/ui_handlers/preferences_example-dark.svg#only-dark)

1. **Edit > Settings…** triggers `on_preferences_requested`, which opens
   `PreferencesDialog` with the current preferences and the available models.
2. On **Accept** the handler keeps `get_preferences()`, saves it to the
   preferences store, and re-applies theme, icons, and window preferences.
3. The status bar says new defaults apply to videos opened from now on.
4. On the next video open, the session handler calls `apply_defaults_to_session`,
   which updates that session's processing settings.

Cancelling the dialog changes nothing.
