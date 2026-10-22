# Infrastructure adapters

Source: `src/app/infrastructure/adapters/`

These adapters wrap concrete infrastructure objects in Application-owned
contracts: detection engines, detection/tracking workers, single-session and
export-all workers, and video-decode controls. They expose the operations
needed by services and managers without making those workflows depend on
concrete worker or engine classes. On the Application side, factory adapters
construct the concrete workers for the current runtime composition.

Adapters preserve the underlying Qt worker lifecycle and forward its signals;
they do not own session lifecycle or choose workflow policy. See [Application
interfaces](../application/interfaces/index.md),
[Application adapters](../application/adapters.md), and the related
[detection](detection/index.md), [export](export.md), [tracking](tracking.md),
and [video](video.md) packages.
