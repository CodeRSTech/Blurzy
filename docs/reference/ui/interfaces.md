# UI interfaces

Source: `src/app/ui/interfaces/`

`UIApplicationInterface` is the facade consumed by handlers for session and
workflow operations; `UIControllerInterface` exposes handler/controller
capabilities to UI composition code. The concrete facade adapter and
controller adapter live in [UI adapters](adapters.md). Compatibility modules
preserve earlier import names; a separate window adapter/interface is
intentionally not implemented.

The [handlers](handlers.md) use these seams to keep workflow requests separate
from widget implementation. Application-owned worker contracts are covered in
[Application interfaces](../application/interfaces/index.md).
