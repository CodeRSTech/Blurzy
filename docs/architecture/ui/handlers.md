# UI handlers

Source: `src/app/ui/handlers`

Qt widgets only emit signals such as "button clicked" or "box dragged". They
do not know what those events *mean*. **A handler is the small object that
turns one family of widget signals into application calls and then refreshes
the screen.** Blurzy has twelve of them, each owning one workflow.

Handlers are the top of the call stack. Everything below them (the
Application facade, services, managers, workers) is Qt-free business logic;
see the [big picture](../big-picture.md) for the whole stack.

## Where handlers sit

![UI handlers call the UIController, then the Application facade, services, managers and finally the session store and workers](../../assets/api/ui_handlers/sits_overview-light.svg#only-light)
![UI handlers call the UIController, then the Application facade, services, managers and finally the session store and workers](../../assets/api/ui_handlers/sits_overview-dark.svg#only-dark)

Arrows are calls. **Handlers run on the GUI thread**; long work is started
through the facade and executes in worker threads that report back with Qt
signals.

## Who owns whom

![UIController creates twelve handlers in four groups; every handler uses the shared Window and Application facade](../../assets/api/ui_handlers/ownership-light.svg#only-light)
![UIController creates twelve handlers in four groups; every handler uses the shared Window and Application facade](../../assets/api/ui_handlers/ownership-dark.svg#only-dark)

Solid arrows show creation: `UIController.__init__` builds every handler and
passes itself in. Dashed arrows show that each handler reads widgets from the
`Window` and calls the `Application` facade.

| Group | Handlers | Article |
| --- | --- | --- |
| Box editing | `AnnotationHandler` | [Annotation handler](handlers/annotation.md) |
| Playback | `PlaybackHandler` | [Playback handler](handlers/playback.md) |
| Rendering, dialogs, preferences | `UIHandler`, `DialogueHandler`, `PreferencesHandler` | [Window, dialogs and preferences](handlers/window-and-dialogs.md) |
| Sessions and projects | `SessionHandler`, `ProjectHandler` | [Sessions and projects](handlers/session-and-projects.md) |
| Detection and tracking | `DetectionHandler`, `TrackingHandler`, `ModelHandler` | [Detection and tracking](handlers/detection-and-tracking.md) |
| Export and import | `ExportHandler`, `ImportExportHandler` | [Export and import](handlers/export-and-import.md) |

!!! note "ModelHandler"
    `ModelHandler` (model loading and switching) is grouped with detection
    here; see the detection-and-tracking article for its coverage.

## The signal-to-refresh loop

![A widget signal reaches a handler slot, which calls the Application facade and then asks the controller to render; errors become dialogs](../../assets/api/ui_handlers/signal_flow-light.svg#only-light)
![A widget signal reaches a handler slot, which calls the Application facade and then asks the controller to render; errors become dialogs](../../assets/api/ui_handlers/signal_flow-dark.svg#only-dark)

Numbers show the usual order for a user action. Dashed arrows are side
channels: worker signals (queued onto the GUI thread by Qt) and error display.

1. A widget emits a signal; the handler connected it in `_connect_signals()`.
2. The slot calls the Application facade. The facade and services own the
   rules and mutate session data.
3. On success the handler asks the controller to render the current frame.
   `UIController.render_frame_for_session_id()` simply delegates to
   `UIHandler.render_saved_frame()`.
4. On failure the handler shows `window.show_error(title, message)`. Errors
   are shown by handlers, never by services.

## How handlers are wired

Every handler receives the `UIController` and stores `controller.window` and
`controller.app`. `DetectionHandler` and `TrackingHandler` instead receive
`controller.ui_controller` and `controller.ui_app`, the narrow
[adapters](adapters.md) that implement the contracts in
[interfaces](interfaces.md). The others still use the concrete objects, so
the adapter migration is partial.

Most handlers are `QObject`s parented to the controller. `UIHandler` is a
plain class because it only renders and has no signals of its own.

![Most handlers talk only to the controller; a few direct calls between handlers exist](../../assets/api/ui_handlers/handler_calls-light.svg#only-light)
![Most handlers talk only to the controller; a few direct calls between handlers exist](../../assets/api/ui_handlers/handler_calls-dark.svg#only-dark)

!!! warning "Current behaviour: handlers do call each other"
    `UIController`'s comments say handlers "should NOT talk to each other".
    Today three direct calls exist (red dashed arrows):
    `ProjectHandler` calls `SessionHandler` (refresh views, initial render),
    and `SessionHandler` calls `PreferencesHandler.apply_defaults_to_session()`
    and `PlaybackHandler.stop_playback()`. `ModelHandler` uses a controller
    dialog factory instead, which is the intended pattern.

## Worked example: one click, end to end

The detailed examples live in the per-handler articles: a delete with undo in
[Annotation handler](handlers/annotation.md#worked-example-delete-and-undo),
a Play click in [Playback handler](handlers/playback.md#worked-example-pressing-play)
and a settings change in
[Window, dialogs and preferences](handlers/window-and-dialogs.md#worked-example-saving-preferences).
All follow the loop above.

## Shared state and keyboard routing

Presentation state shared across handlers lives on the window, not in the
handlers: see [UI view state](view_state.md). `UIController` also installs a
`FrameTableKeyFilter` on the window and both data tables so arrow keys, Delete
and Ctrl shortcuts reach `AnnotationHandler`.

Concrete dialogs, preview widgets and the [main window](qt/window.md) are the
interaction surface. Exact methods are in the
[API reference](../../reference/api/index.md).
