# Detection engine

Source: `src/app/infrastructure/detection/engine`

The factory creates a model-backed `DetectionEngine`. The engine owns the
selected provider model, runs per-frame inference, and maps provider output to
domain detection results. Provider-specific loading and mapping live under
[models](model.md); video-wide frame iteration is handled by the
[detection worker](worker.md), not by the engine.

Supported model names are maintained in
`src/app/infrastructure/detection/model/names.py`; the generated engine API
page derives its provider catalog from those registries. No second list is
maintained in this package note.

The Application manager owns engines per session and coordinates model
selection. See [Application managers](../../application/managers.md).