# Application services

Source: `src/app/application/services`

A **service** is the code that carries out one use case, such as "start
detection" or "save the project". It checks that the request makes sense,
performs the steps in order, and records the outcome. The `Application` facade
creates every service in its constructor and forwards UI requests to them, so
the facade stays thin.

![UI handlers call the facade, which delegates to detection, tracking, session/project and export services; services use managers and infrastructure and write session layers](../../../assets/api/app_services/map-light.svg#only-light)
![UI handlers call the facade, which delegates to detection, tracking, session/project and export services; services use managers and infrastructure and write session layers](../../../assets/api/app_services/map-dark.svg#only-dark)

Solid arrows are calls down the stack. Dashed arrows mark indirect use:
services ask infrastructure factories for workers or stores, and workers
report back to handlers through Qt signals.

## Which page covers what

| Service group | What it does | Page |
| --- | --- | --- |
| `DetectionService`, `DetectionExecutionService`, `DetectionBatchProcessor` | Whole-video and current-frame detection into layers A/B | [Detection](detection.md) |
| `TrackingService`, `TrackingResultProcessor` | Start tracking from A/B and commit results to C/D | [Tracking](tracking.md) |
| `SessionService`, `ProjectService` | Open videos, switch sessions, update settings, save/load `.blurzy` projects | [Session and project](session-project.md) |
| `ExportService` | Render the blurred video from D (or C) | [Video export](export.md) |
| Layer, import and export services (A-D editing, JSON/CSV) | Edit layers and exchange them as files | [Layer services](layers.md), [helpers](helpers.md) |
| `ViewModelService` | Placeholder bound to the facade; defines no operations yet | below |

Managers (engine, tracking worker, decode worker, session registry) are
described in [Managers](../managers.md).

## Common shape of a service

1. **Resolve the session** through an adapter (`get_session_by_id`).
2. **Validate**: no worker already running, a model selected, a usable source
   layer. Failures raise application exceptions that handlers turn into dialogs.
3. **Delegate lifecycle** to a manager or a factory adapter.
4. **Write results** into layers through the session data store.
5. **Log** at the boundary with the session id.

!!! note "`ViewModelService` is a stub"
    `view_model_service.py` only stores the application reference. It has no
    methods, so no view-model behaviour lives there today.

!!! tip "Where to change what"
    Business rules belong in a service or the domain; screen orchestration
    belongs in a UI handler; thread work belongs in an infrastructure worker.
    See [Application](../index.md) for the full boundary description.

Exact signatures are in the [generated API reference](../../../reference/api/index.md).
