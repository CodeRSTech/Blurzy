# Architecture

Blurzy is a PySide6 desktop application with four broad source layers under
`src/app`. The boundaries keep UI code focused on presentation and user input,
while video and machine-learning libraries remain in infrastructure.

## Layer responsibilities

- **Domain** (`app/domain`) defines core types and rules for videos, sessions,
  detections, tracking, and export.
- **Application** (`app/application`) coordinates domain operations through
  services, managers, and interfaces.
- **Infrastructure** (`app/infrastructure`) adapts video decoding, model
  providers, tracking algorithms, persistence, and export workers.
- **UI** (`app/ui`) contains the Qt window/widgets, event handlers, view state,
  and controller.

## Detection flow

1. A user starts detection from a UI widget.
2. A handler delegates the request through the application facade.
3. A detection service prepares the operation and creates a worker through its
   factory/interface.
4. The infrastructure worker calls the selected engine/model and emits results
   and progress.
5. Application/UI handlers update session state and present progress/results.

The same general boundary pattern is used for video decoding, tracking, and
export. This keeps long-running work out of the GUI event loop and provides
clear seams for unit tests and alternate infrastructure implementations.

## Finding your way around

- Application entry point and Qt bootstrap: `src/main.py`
- Workflow composition: `src/app/application/application.py`
- User-action handlers: `src/app/ui/handlers/`
- Qt interface: `src/app/ui/qt/`
- Domain types: `src/app/domain/`
- Video/model/tracking/export implementations: `src/app/infrastructure/`
- Tests organized by source layer: `tests/`

The architecture is evolving alongside the application; these boundaries
describe the current organization rather than a guarantee that every module
already follows them perfectly.
