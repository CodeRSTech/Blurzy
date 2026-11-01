# Application

Source: `src/app/application`

The Application layer decides **what should happen** when the user asks Blurzy
to do something: run detection, track objects, save a project, export a video.
The UI owns windows and dialogs; infrastructure owns models, video files, and
threads; Application sits between them and turns requests into checked,
ordered steps.

![UI handlers call the Application facade, which delegates to services; services use managers and infrastructure workers and write session layers](../../assets/api/app_services/map-light.svg#only-light)
![UI handlers call the Application facade, which delegates to services; services use managers and infrastructure workers and write session layers](../../assets/api/app_services/map-dark.svg#only-dark)

Solid arrows are calls; dashed arrows are indirect or signal-based. Handlers
call the **facade**, the facade delegates, and services use managers and
infrastructure to do the work.

| Part | Role in one sentence | Page |
| --- | --- | --- |
| Facade (`Application`) | One thin object the UI calls; it creates the services and forwards requests | [Services map](services/index.md) |
| Services | Validate a use case, sequence its steps, and write results into layers A-D | [Services](services/index.md) |
| Managers | Own long-lived per-session objects: engines, tracking worker, decode worker, session registry | [Managers](managers.md) |
| Adapters / interfaces | Application-owned contracts plus factories that build concrete workers | covered inside the pages above |

!!! info "Ownership boundaries"
    Application code never touches Qt widgets. **Handlers own user-facing
    dialogs and connect most worker signals**; services own validation, layer
    writes, and logging at the failure boundary. Workers do the slow work on
    background threads.

!!! warning "Not a strict dependency-inversion boundary"
    Services and managers import some concrete infrastructure classes
    (for example `ProjectStore`, and lazily the detection and tracking
    workers). Video rendering itself lives in the Application export service.
    The layout is a convention to follow, not an enforced Clean Architecture.

## Who runs on which thread

![GUI-thread handlers and services start background detection, tracking, and export workers, which report back by Qt signals](../../assets/api/app_services/threads-light.svg#only-light)
![GUI-thread handlers and services start background detection, tracking, and export workers, which report back by Qt signals](../../assets/api/app_services/threads-dark.svg#only-dark)

Solid arrows start work; dashed arrows are signals coming back. Detection
batches return to `DetectionService`, while tracking completion and export
progress are handled by UI handlers.

!!! note "Thread-affinity limitation"
    `DetectionService` is a plain Python object (not a `QObject`), yet its
    batch slot's docstring says it runs on the main thread. Qt cannot use
    object thread affinity for such a receiver, so this guarantee is **not
    established by the service code itself**; treat it as unverified.

## Layers A-D in the services

Detection writes **A** (detector output) and **B** (reviewed copy). Tracking
reads A or B and writes **C** (machine tracks) and **D** (editable tracks).
Export reads **D**, falling back to **C**. Services keep machine output and
manual edits apart; see [Detection](services/detection.md) and
[Tracking](services/tracking.md).

## Pages

- [Services map](services/index.md) - how the pieces connect
- [Detection services](services/detection.md)
- [Tracking services](services/tracking.md)
- [Session and project services](services/session-project.md)
- [Video export service](services/export.md)
- [Layer services](services/layers.md) and [helpers](services/helpers.md)
- [Managers](managers.md)

See also the [architecture overview](../overview.md) and the
[generated API reference](../../reference/api/index.md).
