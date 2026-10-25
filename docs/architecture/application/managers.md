# Application managers

Source: `src/app/application/managers`

Application managers own selected session-scoped resources and lifecycle
transitions; services still decide when a use case should run.

| Manager | Owns or coordinates | Key boundary |
| --- | --- | --- |
| `SessionManager` | Open sessions and active-session selection | Creates a session shell, delegates runtime setup to `SessionInitializer`, and closes resources when a session is discarded. |
| `SessionInitializer` | Runtime assembly for one session | Opens the reader, derives `SessionState` from metadata, starts the decode worker, and attaches them to the session. |
| `VideoDecodeWorkerManager` | Decode worker activation | Activates the current session's buffer from the playhead and deactivates the previous one to release its buffered frames. |
| `DetectionEngineManager` | Per-session model engines | Reuses or replaces the engine associated with a session/model selection. |
| `TrackingWorkerManager` | Tracking worker transitions | Validates source layer and input data, snapshots detections, clears C/D, then starts/stops and reads the worker. |

The UI calls the Application facade; it does not start workers or swap session
resources directly. Services use managers for worker lifecycle but retain
workflow rules such as whether a layer should be cleared or when results are
synchronized. This separation is why worker cleanup and data-layer writes
should be checked in both the service and manager before changing a lifecycle.

See [session infrastructure](../infrastructure/session.md),
[detection services](services/detection.md), and
[tracking services](services/tracking.md) for complete flows.
