# Export-all interfaces

Source: `src/app/application/interfaces/export_all/`

This contract pair creates and controls the background worker for exporting
multiple sessions. It represents a batch operation, separate from the
single-session worker in [Export](export.md); the factory keeps worker creation
behind the Application boundary, and the worker exposes the standard Qt start,
stop, running-state, and deferred-deletion lifecycle.

The concrete implementation is in [export infrastructure](../../infrastructure/export.md).
Batch orchestration and result presentation belong to the calling workflow,
not the interface itself.
