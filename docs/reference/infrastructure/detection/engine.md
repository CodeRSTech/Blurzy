# Detection engine

Source: `src/app/infrastructure/detection/engine/`

The engine factory creates a model-backed `DetectionEngine`. The engine
loads the selected provider model, runs per-frame inference, and maps output
to domain detection results.

Supported model names are maintained in
`src/app/infrastructure/detection/model/names.py`. The generated
`DetectionEngine` API page includes the registry names grouped by provider;
the catalog is derived from this source rather than maintained separately.

## Supported model names

### Torch
- `...`

### Ultralytics
- `...`

### MTCNN
- `...`, 'ULTRALYTICS_YOLO_MODELS', 'MTCNN_MODELS']