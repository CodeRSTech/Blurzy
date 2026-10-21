# Application adapters

Source: `src/app/application/adapters/`

Application adapters provide the concrete bindings used by the facade and
services. `ApplicationAdapter` exposes the application through the narrower UI
contract; worker-factory adapters create infrastructure detection, tracking,
single-session export, and export-all workers behind Application-owned
interfaces. This keeps workflow code dependent on contracts while leaving the
current runtime composition explicit.

The adapters are composition seams, not the owners of worker or session
lifecycle. Managers and services retain that responsibility. See [interfaces](interfaces/index.md),
[managers](managers.md), and [Infrastructure adapters](../infrastructure/adapters.md).
