# Detection services

Source: `src/app/application/services/detection`

Detection services split current-frame inference from video-wide work.
`DetectionExecutionService` uses the per-session engine manager for a
single-frame request. `DetectionService` validates and starts background
detection through the worker factory; `DetectionBatchProcessor` stores selected
results in Layer A and filtered editable copies in Layer B. The layer service
owns Layer B edits, and import/export collaborators handle annotation files
separately from video rendering.

The worker and model implementations are in
[detection infrastructure](../../infrastructure/detection/index.md). The
broader A/B/C/D layer roles are summarized in [Architecture](../../overview.md).
