# Application

Source: `src/app/application/`

The Application layer exposes a facade to the UI and coordinates use cases
through services, managers, adapters, and interfaces. The facade composes
workflow services and session ownership; services validate and sequence
operations, managers own selected long-lived session and worker lifecycles,
and adapters bind contracts to current infrastructure implementations.
Application code uses domain state and does not make Qt widgets part of service
logic.

At runtime, UI handlers call the facade, services coordinate work against
session data and domain values, and workers report results through contracts
and signals. See [Architecture](../../architecture.md) for the end-to-end flows.

## Packages

- [Adapters](adapters.md)
- [Interfaces](interfaces/index.md)
- [Managers](managers.md)
- [Services](services/index.md)
