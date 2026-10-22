# Detection interfaces

Source: `src/app/application/interfaces/detection/`

These contracts separate detection orchestration from model and thread
implementations. The engine contract runs inference and switches the selected
model; its factory creates engines. The worker contract controls a background
frame-processing run and exposes its cached results, while the worker factory
creates the worker used by the detection service.

The concrete engine and worker are in [detection infrastructure](../../infrastructure/detection/index.md);
the application-side factory binding is in [adapters](../adapters.md). The
service and session data flow are described in [Detection services](../services/detection.md).
