# Test Suite Layout (Mirrors `src/app`)

This test suite uses `src/app` as the canonical architecture map.

## Why

- Keeps ownership clear as test count grows.
- Makes failures easier to triage by layer/sub-layer.
- Prevents flat-folder crowding in `tests`.

## Directory Policy

- `tests/application/**` mirrors `src/app/application/**`
- `tests/domain/**` mirrors `src/app/domain/**`
- `tests/infrastructure/**` mirrors `src/app/infrastructure/**`
- `tests/ui/**` mirrors `src/app/ui/**`
- `tests/shared/**` is for shared fixtures/builders/factories used by multiple layers.
- `tests/integration/**` is for cross-layer or runtime-flow tests.
- `tests/assets/**` is for heavy/static test artifacts (frames, models, sample files).

## Strict 1:1 Mirror Skeleton

The following mirror skeleton exists (including currently empty branches):

- `tests/application/adapters`
- `tests/application/interfaces/detection`
- `tests/application/interfaces/export`
- `tests/application/interfaces/export_all`
- `tests/application/interfaces/session`
- `tests/application/interfaces/tracking`
- `tests/application/interfaces/video`
- `tests/application/managers`
- `tests/application/services/detection`
- `tests/application/services/tracking`
- `tests/domain/base`
- `tests/domain/detection`
- `tests/domain/export`
- `tests/domain/helpers`
- `tests/domain/session`
- `tests/domain/tracking`
- `tests/domain/video`
- `tests/domain/views`
- `tests/infrastructure/adapters`
- `tests/infrastructure/detection/engine`
- `tests/infrastructure/detection/model/mtcnn_tf`
- `tests/infrastructure/detection/model/mtcnn_torch`
- `tests/infrastructure/detection/model/torch`
- `tests/infrastructure/detection/model/yolo`
- `tests/infrastructure/detection/worker`
- `tests/infrastructure/export`
- `tests/infrastructure/session`
- `tests/infrastructure/tracking`
- `tests/infrastructure/video`
- `tests/infrastructure/views`
- `tests/ui/adapters`
- `tests/ui/handlers`
- `tests/ui/interfaces`
- `tests/ui/qt/containers`
- `tests/ui/qt/data`
- `tests/ui/qt/dialogue_boxes`
- `tests/ui/qt/shared`
- `tests/ui/qt/utilities`
- `tests/ui/qt/widgets`
- `tests/ui/state`

Also created for workflow separation:

- `tests/integration/entrypoints`
- `tests/integration/pipeline`
- `tests/integration/workers`
- `tests/assets/frames`
- `tests/assets/models`

## Placement Rules

1. Unit test a symbol in the closest mirrored folder to its source file.
2. If test covers multiple layers, place under `tests/integration/**`.
3. Use `test_<symbol>.py` for unit-level tests.
4. Use `test_<flow>_integration.py` for integration tests.
5. Path/hardware-dependent tests may be marked temporarily (`xfail` or marker) during migration.

## Migration Notes

- Rewrite corrupted tests immediately:
  - `tests/domain/helpers/test_domain_filters.py`
  - `tests/infrastructure/detection/model/test_detection_model_helpers.py`
- Keep only environment-coupled tests temporarily marked while being stabilized.

## Initial File Move Map (Top-Level -> Mirrored)

- `tests/test_adapter_wiring.py` -> `tests/infrastructure/adapters/test_adapter_wiring.py`
- `tests/test_base_box.py` -> `tests/domain/base/test_base_box.py`
- `tests/test_detection_batch_processor.py` -> `tests/application/services/detection/test_detection_batch_processor.py`
- `tests/test_detection_engine_manager.py` -> `tests/application/managers/test_detection_engine_manager.py`
- `tests/test_detection_execution_service.py` -> `tests/application/services/detection/test_detection_execution_service.py`
- `tests/test_detection_service_facade.py` -> `tests/application/services/detection/test_detection_service_facade.py`
- `tests/test_tracking_result_processor.py` -> `tests/application/services/tracking/test_tracking_result_processor.py`
- `tests/test_tracking_service_facade.py` -> `tests/application/services/tracking/test_tracking_service_facade.py`
- `tests/test_tracking_worker_manager.py` -> `tests/application/managers/test_tracking_worker_manager.py`
- `tests/test_video_decode_worker_manager.py` -> `tests/application/managers/test_video_decode_worker_manager.py`
- `tests/test_video_ring_buffer.py` -> `tests/domain/video/test_video_ring_buffer.py`
- `tests/test_hungarian_iou_tracker.py` -> `tests/infrastructure/tracking/test_hungarian_iou_tracker.py`
- `tests/test_session_data_store.py` -> `tests/infrastructure/session/test_session_data_store.py`
- `tests/test_session_runtime_state.py` -> `tests/domain/session/test_session_runtime_state.py`
- `tests/test_session_service.py` -> `tests/application/services/test_session_service.py`
- `tests/test_runtime_config.py` -> `tests/shared/test_runtime_config.py`
- `tests/test_main.py` -> `tests/integration/entrypoints/test_main.py`
- `tests/video_decode_worker_test.py` -> `tests/integration/workers/test_video_decode_worker_integration.py`
- `tests/test_domain_filters.py` -> `tests/domain/helpers/test_domain_filters.py`
- `tests/test_detection_model_helpers.py` -> `tests/infrastructure/detection/model/test_detection_model_helpers.py`
- `tests/detection_layer_service_tests.py` -> `tests/application/services/detection/test_detection_layer_service.py`
- `tests/annotation_context_actions_test.py` -> `tests/domain/detection/test_annotation_context_actions.py`

Assets and sandbox migration:

- `tests/*.pt` -> `tests/assets/models/*.pt`
- `tests/test_frames/**` -> `tests/assets/frames/**`
- `tests/by_me/**` -> `tests/integration/pipeline/by_me/**`

## Quick Run Examples

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q
```

```powershell
$env:PYTHONPATH = "src"
python -m pytest tests/domain/helpers -q
```

