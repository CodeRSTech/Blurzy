# Application

Source: `src/app/application`

The Application layer is the workflow coordinator between the UI and
infrastructure. The UI calls a facade, services validate and sequence use
cases, managers own selected long-lived session/worker lifecycles, and
adapters connect application-owned contracts to concrete infrastructure
implementations. Application policy uses domain values and does not manipulate
Qt widgets.

For example, detection service code validates model/session state, asks a
manager/factory for a worker, and processes its emitted batches into A/B.
Tracking similarly validates an A/B source and synchronizes completed output
into C/D. The worker performs frame/model/tracker work in the background;
Application owns the meaning and placement of its results.

This is not yet a strict dependency-inversion boundary: some Application
composition and lifecycle code imports concrete infrastructure classes.
`src/main.py` wires the top-level runtime and the facade coordinates services;
see the [architecture overview](../overview.md),
[managers](managers.md), and [services](services/index.md).

## Packages

- [Managers](managers.md)
- [Services](services/index.md)
