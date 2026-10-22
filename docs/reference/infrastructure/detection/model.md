# Detection models

Source: `src/app/infrastructure/detection/model/`

This package defines the model protocol and common helpers, resolves model
names through the loader, and contains provider integrations and output
mappers for TorchVision, Ultralytics YOLO, and MTCNN. The literal registries in
`names.py` are the source of supported model names; the generated engine API
catalog reads them directly. Model loading and inference are invoked through
the [detection engine](engine.md), not from UI widgets.

Provider-specific dependencies and weight availability depend on the selected
integration and runtime; this package note does not claim a single download or
licensing policy. See the [detection package overview](index.md) and
[engine lifecycle](engine.md).
