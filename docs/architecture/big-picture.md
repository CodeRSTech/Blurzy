# The big picture

Blurzy is a desktop app that finds people or objects in video, tracks them,
lets you correct the result, and exports a copy with chosen subjects blurred.
The component pages explain one part at a time; this page shows **how the parts
cooperate** so each detailed page has a place to land.

## Who owns what

![Stack from window and handlers through the controller and Application facade to services, managers, workers, and session storage](../assets/api/big_picture/stack-light.svg#only-light)
![Stack from window and handlers through the controller and Application facade to services, managers, workers, and session storage](../assets/api/big_picture/stack-dark.svg#only-dark)

Solid arrows are **calls** that go down the stack; the dashed arrow is a set of
**Qt signals** that come back up from background workers.

| Part | Job in one sentence | Read more |
| --- | --- | --- |
| Window and widgets | Draw the preview, tables, and panels and emit Qt signals when the user acts | [UI](ui/index.md) |
| Handlers | Turn one family of user actions into facade calls, then show progress, errors, and refreshed views | [UI handlers](ui/handlers.md) |
| `UIController` | Owns the handlers and adapters and exposes window-level helpers such as "redraw this frame" | [UI handlers](ui/handlers.md) |
| `Application` facade | One thin entry point; every method forwards to a service or the session manager | [Application](application/index.md) |
| Services | Decide *whether and how* a use case runs: validation, layer rules, import/export | [Services](application/services/index.md) |
| Managers | Own session and worker **lifecycles**: create, start, stop, switch, clean up | [Managers](application/managers.md) |
| Workers and stores | Do the slow work off the GUI thread and hold the live data | [Infrastructure](infrastructure/index.md) |

!!! note "Where decisions live"

    Handlers never run detection or tracking themselves, and workers never touch
    widgets. Services hold the rules ("B seeds from A", "block tracking while
    detection runs"); managers hold lifecycles; handlers own dialogs.

## How the app is assembled

![main.py creates the Application, the Window, and the UIController, whose adapters wrap the facade and whose handlers connect widget signals, before the Qt event loop starts](../assets/api/big_picture/startup-light.svg#only-light)
![main.py creates the Application, the Window, and the UIController, whose adapters wrap the facade and whose handlers connect widget signals, before the Qt event loop starts](../assets/api/big_picture/startup-dark.svg#only-dark)

`src/main.py` is the only composition root. The `Application` constructor
builds the `SessionManager` and every service; `UIController` then builds its
adapters and twelve handlers, and each handler connects the widget signals it
cares about. After that, everything is driven by user events and worker signals
inside the Qt event loop.

## Which thread does what

![The GUI thread calls into the facade, services, and managers, which start background workers; workers report back only through Qt signals](../assets/api/big_picture/threads-light.svg#only-light)
![The GUI thread calls into the facade, services, and managers, which start background workers; workers report back only through Qt signals](../assets/api/big_picture/threads-dark.svg#only-dark)

Solid arrows are calls from the GUI thread; the dashed arrow is signal traffic
back. Decoding, detection, tracking, and export run on their own threads so the
window stays responsive. Workers emit signals and never touch widgets;
the handler slots that receive those signals update the UI.

!!! warning "Not everything is off-thread"

    Layer import/export and the final write of tracking results into the
    session layers happen on the GUI thread, and large imports have no progress
    bar or cancellation. See [layer services](application/services/layers.md).

## One user action, end to end: Start tracking

![Sequence from the Start tracking click through the handler, facade, service, manager, and background worker to the session layers and the refreshed preview](../assets/api/big_picture/tracking_journey-light.svg#only-light)
![Sequence from the Start tracking click through the handler, facade, service, manager, and background worker to the session layers and the refreshed preview](../assets/api/big_picture/tracking_journey-dark.svg#only-dark)

Read top to bottom; arrows are method calls or Qt signals.

1. **Validate in the handler.** It checks that a session is selected and active
   and refuses to start while detection or tracking is running. If detection
   covered only part of the video, it asks the user to confirm.
2. **Pass through the facade.** `Application` forwards the request to
   `TrackingService` without adding logic.
3. **Prepare in the manager.** `TrackingWorkerManager` validates the source
   layer, snapshots its boxes, **clears Layers C and D**, and starts the worker.
4. **Work in the background.** The worker runs the chosen strategy and emits
   progress; the handler updates the progress bar.
5. **Commit and refresh.** On `finished_processing` the handler asks the
   service to write the result into Layer C and seed Layer D, then selects the
   Tracking tab and redraws the preview.

??? example "The same shape applies to detection and export"

    Detection replaces step 3 with a `DetectionService` call that prepares an
    engine and starts a `DetectionWorker` that fills Layer A in batches. Export
    starts an export worker that reads Layer D (or C) and writes a blurred video.
    Only the service rules, worker, and signals differ.

!!! warning "Current behaviour to know about"

    - Starting tracking clears C and D *before* the worker exists, so manual
      edits in D are discarded and a factory error leaves both layers empty.
    - `finished_processing` is also emitted after a worker error, so the handler
      can still sync an empty result into C.
    - Handlers are documented as talking only to the controller, but some
      currently call each other (for example the project handler calls the
      session handler).

## The data that flows through it

Every workflow reads or writes the four annotation layers kept in the session
store: **A** detector output, **B** reviewed detections, **C** tracker output,
**D** reviewed tracks. See [annotation layers](domain/video.md) for the
seeding rules and how export chooses between D and C.

## Where to go next

- **Follow a workflow:** [Detection worker](infrastructure/detection/worker.md),
  [Tracking](infrastructure/tracking.md), [Video playback](infrastructure/video.md),
  [Session storage](infrastructure/session.md), [Export](infrastructure/export.md).
- **See who triggers it:** [UI handlers](ui/handlers.md) and
  [Application services](application/services/index.md).
- **See what keeps it alive:** [Application managers](application/managers.md).
- **Look up an exact contract:** the [API reference](../reference/api/index.md).
