# Application managers

Source: `src/app/application/managers/`

Managers own selected long-lived resources rather than deciding whole use
cases. `SessionManager` owns the open-session collection and active-session
selection; `SessionInitializer` creates and attaches each session's runtime
state, data store, video reader, and decode worker. `VideoDecodeWorkerManager`
switches decode-worker activity with the active session, while
`DetectionEngineManager` keeps model engines per session and
`TrackingWorkerManager` coordinates tracking-worker start/stop transitions.

Services call managers as part of workflows; the UI asks the facade rather
than manipulating these resources directly. Session initialization and worker
cleanup are workflow-specific, so consult the relevant service and manager
before changing lifecycle behavior. Related: [services](services/index.md),
[interfaces](interfaces/index.md), and [session infrastructure](../infrastructure/session.md).
