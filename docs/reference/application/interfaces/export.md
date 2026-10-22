# Export interfaces

Source: `src/app/application/interfaces/export/`

The single-session export factory and worker contracts isolate Application
workflows from the Qt worker that performs a long-running video export. The
worker can be started, asked to stop, queried while active, and allowed to
finish and clean up through its Qt lifecycle. Export progress and outcome are
reported through the worker's signals; rendering itself is coordinated by the
Application export service.

See [export infrastructure](../../infrastructure/export.md),
[service helpers and workflows](../services/index.md), and the distinct
[export-all contract](export_all.md).
