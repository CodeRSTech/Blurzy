"""Detection model registry and confidence thresholds for Torch and YOLO variants."""

from __future__ import annotations

# Map UI display name → (TorchVision model function, weights class) for dynamic loading
TORCH_MODELS: dict[str, tuple[str, str]] = {
    "Torch FCOS_ResNet50_FPN": (
        "fcos_resnet50_fpn",
        "FCOS_ResNet50_FPN_Weights",
    ),
    "Torch FasterRCNN_MobileNet_V3_Large_320_FPN": (
        "fasterrcnn_mobilenet_v3_large_320_fpn",
        "FasterRCNN_MobileNet_V3_Large_320_FPN_Weights",
    ),
    "Torch FasterRCNN_MobileNet_V3_Large_FPN": (
        "fasterrcnn_mobilenet_v3_large_fpn",
        "FasterRCNN_MobileNet_V3_Large_FPN_Weights",
    ),
    "Torch FasterRCNN_ResNet50_FPN_V2": (
        "fasterrcnn_resnet50_fpn_v2",
        "FasterRCNN_ResNet50_FPN_V2_Weights",
    ),
    "Torch FasterRCNN_ResNet50_FPN": (
        "fasterrcnn_resnet50_fpn",
        "FasterRCNN_ResNet50_FPN_Weights",
    ),
    "Torch RetinaNet_ResNet50_FPN_V2": (
        "retinanet_resnet50_fpn_v2",
        "RetinaNet_ResNet50_FPN_V2_Weights",
    ),
    "Torch RetinaNet_ResNet50_FPN": (
        "retinanet_resnet50_fpn",
        "RetinaNet_ResNet50_FPN_Weights",
    ),
    "Torch SSD300_VGG16": (
        "ssd300_vgg16",
        "SSD300_VGG16_Weights",
    ),
    "Torch SSDLite320_MobileNet_V3_Large": (
        "ssdlite320_mobilenet_v3_large",
        "SSDLite320_MobileNet_V3_Large_Weights",
    ),
}

# Map UI display name → .pt model file name (loaded dynamically by Ultralytics)
ULTRALYTICS_YOLO_MODELS: dict[str, str] = {
    # YOLOv3 (Modernized 'u' variants)
    "YOLOv3-tiny": "yolov3-tinyu.pt",
    "YOLOv3": "yolov3u.pt",
    "YOLOv3-spp": "yolov3-sppu.pt",
    # YOLOv5 ('u' variants optimized for the Ultralytics v8+ codebase)
    "YOLOv5n": "yolov5nu.pt",
    "YOLOv5s": "yolov5su.pt",
    "YOLOv5m": "yolov5mu.pt",
    "YOLOv5l": "yolov5lu.pt",
    "YOLOv5x": "yolov5xu.pt",
    # YOLOv6 (Supported via Meituan partnership)
    # "YOLOv6n": "yolov6n.pt",
    # "YOLOv6s": "yolov6s.pt",
    # "YOLOv6m": "yolov6m.pt",
    # "YOLOv6l": "yolov6l.pt",
    # "YOLOv6x": "yolov6x.pt",
    # YOLOv8
    "YOLOv8n": "yolov8n.pt",
    "YOLOv8s": "yolov8s.pt",
    "YOLOv8m": "yolov8m.pt",
    "YOLOv8l": "yolov8l.pt",
    "YOLOv8x": "yolov8x.pt",
    # YOLOv9 (Note the unique scale suffixes: tiny, custom, extended)
    "YOLOv9t": "yolov9t.pt",
    "YOLOv9s": "yolov9s.pt",
    "YOLOv9m": "yolov9m.pt",
    "YOLOv9c": "yolov9c.pt",
    "YOLOv9e": "yolov9e.pt",
    # YOLOv10 (Includes a 'base' model 'b')
    "YOLOv10n": "yolov10n.pt",
    "YOLOv10s": "yolov10s.pt",
    "YOLOv10m": "yolov10m.pt",
    "YOLOv10b": "yolov10b.pt",
    "YOLOv10l": "yolov10l.pt",
    "YOLOv10x": "yolov10x.pt",
    # YOLO11 (Ultralytics officially dropped the 'v' starting with 11)
    "YOLO11n": "yolo11n.pt",
    "YOLO11s": "yolo11s.pt",
    "YOLO11m": "yolo11m.pt",
    "YOLO11l": "yolo11l.pt",
    "YOLO11x": "yolo11x.pt",
    # YOLO12 (Attention-centric architecture)
    "YOLO12n": "yolo12n.pt",
    "YOLO12s": "yolo12s.pt",
    "YOLO12m": "yolo12m.pt",
    "YOLO12l": "yolo12l.pt",
    "YOLO12x": "yolo12x.pt",
    # YOLO26 (Latest end-to-end NMS-free model; preserving 'v26' keys)
    "YOLOv26n": "yolo26n.pt",
    "YOLOv26s": "yolo26s.pt",
    "YOLOv26m": "yolo26m.pt",
    "YOLOv26l": "yolo26l.pt",
    "YOLOv26x": "yolo26x.pt",
    # YOLO-NAS (Neural Architecture Search foundational model by Deci AI)
    # "YOLO-NAS-s": "yolo_nas_s.pt",
    # "YOLO-NAS-m": "yolo_nas_m.pt",
    # "YOLO-NAS-l": "yolo_nas_l.pt",
}

MTCNN_MODELS = (
    "MTCNN-Tensorflow",
    "MTCNN-Pytorch",
)

# Minimum confidence score to accept a detection (filters low-confidence predictions)
DEFAULT_TORCH_CONFIDENCE_THRESHOLD = 0.50
DEFAULT_YOLO_CONFIDENCE_THRESHOLD = 0.25
DEFAULT_MTCNN_TF_CONFIDENCE_THRESHOLD = 0.90
DEFAULT_MTCNN_TORCH_CONFIDENCE_THRESHOLD = 0.90