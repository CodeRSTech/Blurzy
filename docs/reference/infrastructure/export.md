# Export infrastructure

Source: `src/app/infrastructure/export/`

Export workers execute longer-running export operations away from the GUI
thread and report progress, success, cancellation, or errors. The current
frame rendering implementation is in `application/services/export_service.py`.

**Expand this stub with:** worker/service boundary and output resource cleanup.

