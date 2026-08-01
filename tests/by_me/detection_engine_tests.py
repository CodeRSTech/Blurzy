from pathlib import Path
from typing import cast

import cv2

from app.domain.helpers.functions import map_detections_to_bbox
from app.domain.detection import DetectionResult
from app.infrastructure.dtypes import RGBFrame
from app.infrastructure.detection.engine import DetectionEngine
from app.infrastructure.detection.model.names import (
    ULTRALYTICS_YOLO_MODELS,
    TORCH_MODELS,
)
from app.infrastructure.detection.engine.detection_engine_factory import DetectionEngineAdapterFactory
from app.shared import draw_frame_overlays

# __file__ is the absolute path to this test script.
# .parent gets the folder the script is in (e.g., .../EasyBlur/tests)
CURRENT_DIR = Path(__file__).parent

# Construct the absolute path to the input image
path_to_image = str(CURRENT_DIR / "test_frames" / "park-1.png")
img = cast(RGBFrame, cv2.imread(path_to_image))
frame = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

# Construct the absolute path to the output directory and create it
output_dir = CURRENT_DIR / "test_frames" / "outputs"
output_dir.mkdir(parents=True, exist_ok=True)


def draw_detection_boxes_on_frame_and_save_to_disk(
    detections: list[DetectionResult],
        input_frame: RGBFrame,
    output_file_path,
):
    boxes = map_detections_to_bbox(detections)
    frame_out = draw_frame_overlays(frame=input_frame, boxes=boxes)

    # Convert back to BGR for saving, otherwise OpenCV will invert Red and Blue!
    bgr_frame_out = cv2.cvtColor(frame_out, cv2.COLOR_RGB2BGR)

    # Save to disk
    # output_path = f"test_frames/outputs/{model_name}_output.png"
    # cv2.imwrite(output_path, bgr_frame_out)

    cv2.imwrite(str(output_file_path), bgr_frame_out)


def test_all_yolo_detection_models():
    # ================================================
    # INITIALIZE DETECTION ENGINE AND FRAME
    # ================================================
    detection_engine_factory = DetectionEngineAdapterFactory()
    detection_engine = None

    # ================================================
    # Iterate over all YOLO model
    # ================================================
    for model_name in ULTRALYTICS_YOLO_MODELS:
        if detection_engine is not None and isinstance(
            detection_engine, DetectionEngine
        ):
            detection_engine.set_model(model_name)
        else:
            detection_engine = detection_engine_factory.create(model_name=model_name)

        # ================================================
        # DETECT FRAME AND CHECK RESULTS
        # ================================================
        detections = detection_engine.detect(frame)
        print(f"Model '{model_name}' parsed {len(detections)} detections in frame")

        assert detections is not None
        assert len(detections) > 0

        output_file_path = output_dir / f"{model_name}_output.png"
        draw_detection_boxes_on_frame_and_save_to_disk(
            detections=detections,
            input_frame=frame,
            output_file_path=output_file_path,
        )


def test_torch_fcos_resnet50_fpn_detection_model():
    # ================================================
    # INITIALIZE DETECTION ENGINE AND FRAME
    # ================================================
    detection_engine_factory = DetectionEngineAdapterFactory()
    detection_engine = None

    # ================================================
    # Iterate over all TORCH model
    # ================================================
    for model_name in TORCH_MODELS:
        if detection_engine is not None and isinstance(
            detection_engine, DetectionEngine
        ):
            detection_engine.set_model(model_name)
        else:
            detection_engine = detection_engine_factory.create(model_name=model_name)

        # ================================================
        # DETECT FRAME AND CHECK RESULTS
        # ================================================
        detections = detection_engine.detect(frame)
        print(f"Model '{model_name}' parsed {len(detections)} detections in frame")

        output_file_path = output_dir / f"{model_name}_output.png"
        draw_detection_boxes_on_frame_and_save_to_disk(
            detections=detections,
            input_frame=frame,
            output_file_path=output_file_path,
        )
        assert detections is not None
        assert len(detections) > 0
