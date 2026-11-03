# Application managers

Source: `src/app/application/managers`

A **manager** is the small object that actually *changes* a session's
long-lived resources: it opens a video, wakes or sleeps a decode thread, swaps a
detection model, or starts a tracking thread. Services decide *whether* a use
case should run; managers know *how* the session's resources are replaced
safely. Read [the whole stack](../big-picture.md) for how requests reach this
layer.

## Where this sits

![Request path: UI handler, UIController or adapter, Application facade, service, managers (highlighted), then infrastructure session and workers](../../assets/api/managers/stack-light.svg#only-light)
![Request path: UI handler, UIController or adapter, Application facade, service, managers (highlighted), then infrastructure session and workers](../../assets/api/managers/stack-dark.svg#only-dark)

Arrows show a request travelling down the stack. Results travel back up as
return values or Qt signals; managers never touch widgets.

## Who owns what

![Services call managers; managers attach, replace or detach resources on the infrastructure Session](../../assets/api/managers/ownership-light.svg#only-light)
![Services call managers; managers attach, replace or detach resources on the infrastructure Session](../../assets/api/managers/ownership-dark.svg#only-dark)

The Application facade also talks to `SessionManager` directly (open, close,
active id). Every other manager is reached through a service.

| Manager | Owns or coordinates | Details |
| --- | --- | --- |
| `SessionManager` | The dictionary of open `Session` objects and the active session id | [Sessions](managers/sessions.md) |
| `SessionInitializer` | One-time assembly of reader, state and decode worker for a new session | [Sessions](managers/sessions.md) |
| `VideoDecodeWorkerManager` | Which session's decode thread is buffering frames | [Sessions](managers/sessions.md) |
| `DetectionEngineManager` | The per-session detection engine (reuse, replace, remove) | [Workers and engines](managers/workers.md) |
| `TrackingWorkerManager` | Tracking worker start, stop and result reads; clears layers C and D | [Workers and engines](managers/workers.md) |

The managers hold no Qt widgets and no business rules about *when* to run;
progress reporting and user dialogs belong to handlers and services.

## Worked example: opening a video

![Sequence from the user choosing a video through the session handler, Application and session service, session manager, initializer and decode worker, to the first frame being rendered](../../assets/api/managers/open-sequence-light.svg#only-light)
![Sequence from the user choosing a video through the session handler, Application and session service, session manager, initializer and decode worker, to the first frame being rendered](../../assets/api/managers/open-sequence-dark.svg#only-dark)

Solid arrows are calls on the GUI thread; the decode worker runs on its own
thread and only starts buffering once the session becomes active. The
[Sessions page](managers/sessions.md) explains each step. A second example,
running tracking end to end, is on [Workers and engines](managers/workers.md).

## Threading at a glance

| Thread | What runs there |
| --- | --- |
| GUI thread | All manager calls, `Session` dictionary changes, active-session switching |
| Decode worker (one per session) | Frame decoding into a ring buffer; guarded by a Qt mutex |
| Tracking worker (one per run) | Association and post-processing on a private copy of the data |

The managers themselves use **no locks**: they assume they are called from the
GUI thread. Thread safety lives inside the workers (see each page).

!!! warning "Limitations in current behaviour"
    - Manager calls are not synchronised; calling them from a worker thread is
      unsupported.
    - Some cleanup paths do not notify other components. The details are on the
      [Sessions](managers/sessions.md#limitations-and-discrepancies) and
      [Workers and engines](managers/workers.md#limitations-and-discrepancies)
      pages.

See also [session infrastructure](../infrastructure/session.md),
[detection services](services/detection.md), and
[tracking services](services/tracking.md). API contracts are in the
[generated reference](../../reference/api/index.md).
