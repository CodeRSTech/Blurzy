"""Generate the opt-in architecture example through the real detection engine."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets" / "api" / "detection_engine"


def file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=ASSETS / "snapshot-original.png",
        help="Input image; defaults to the published original for regeneration.",
    )
    args = parser.parse_args()
    weights = ROOT / "yolov8n.pt"
    if Path.cwd().resolve() != ROOT:
        parser.error("Run this script from the repository root.")
    if not args.input.is_file():
        parser.error(f"Input image does not exist: {args.input}")
    if not weights.is_file():
        parser.error("Local yolov8n.pt weights are required; this script will not download them.")

    sys.path.insert(0, str(ROOT / "src"))
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    from loguru import logger
    from app.infrastructure.detection.engine.detection_engine import DetectionEngine

    warnings: list[str] = []
    sink = logger.add(lambda message: warnings.append(str(message)), level="WARNING")
    try:
        with Image.open(args.input) as source:
            original = source.convert("RGB")
        frame = np.array(original)
        engine = DetectionEngine("YOLOv8n")
        detections = engine.detect(frame)
    finally:
        logger.remove(sink)
    if warnings:
        raise RuntimeError("Refusing to publish a run with warnings:\n" + "\n".join(warnings))
    if not detections:
        raise RuntimeError("Expected nonempty snapshot detections; inspect logs before publishing.")

    width, height = original.size
    records = [asdict(detection) for detection in detections]
    for detection in detections:
        x1, y1, x2, y2 = detection.bbox_xyxy
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            raise ValueError(f"Invalid example box: {detection!r}")
        if not 0 <= detection.confidence <= 1:
            raise ValueError(f"Invalid example confidence: {detection!r}")

    annotated = original.copy()
    draw = ImageDraw.Draw(annotated)
    font = ImageFont.load_default(size=12)
    for detection in detections:
        x1, y1, x2, y2 = detection.bbox_xyxy
        draw.rectangle((x1, y1, x2, y2), outline=detection.color_hex, width=2)
        # Short IDs keep the crowded scene readable; the JSON carries full fields.
        text = detection.item_id.removeprefix("yolo-")
        bounds = draw.textbbox((0, 0), text, font=font)
        text_width = bounds[2] - bounds[0] + 6
        text_height = bounds[3] - bounds[1] + 6
        left = min(x1, width - text_width)
        top = max(0, y1 - text_height)
        draw.rectangle((left, top, left + text_width, top + text_height), fill="#161b22")
        draw.text((left + 3, top + 3 - bounds[1]), text, fill="white", font=font)

    ASSETS.mkdir(parents=True, exist_ok=True)
    original_path = ASSETS / "snapshot-original.png"
    original.save(original_path)
    annotated.save(ASSETS / "snapshot-annotated.png")
    payload = {
        "model_name": engine.model_name,
        "weights": {"filename": weights.name, "sha256": file_hash(weights)},
        "input": {
            "filename": original_path.name,
            "sha256": file_hash(original_path),
            "rgb_pixels_sha256": sha256(frame.tobytes()).hexdigest(),
            "width": width,
            "height": height,
            "dtype": str(frame.dtype),
            "channel_order": "RGB, passed unchanged through the engine to the YOLO wrapper",
            "attribution": "User-supplied MOT17-04-SDP-snapshot.png; exact origin and redistribution permission unverified.",
        },
        "packages": {
            name: version(name) for name in ("Blurzy", "ultralytics", "torch", "torchvision", "numpy", "Pillow")
        },
        "python": sys.version.split()[0],
        "settings": {
            "confidence": 0.25,
            "nms_iou": 0.45,
            "chosen_labels": None,
            "other_provider_options": "Installed Ultralytics defaults",
        },
        "annotation": "Numbers are the suffix of item_id (for example 7 means yolo-7).",
        "count": len(records),
        "counts_by_label": dict(sorted(Counter(d.label for d in detections).items())),
        "detections": records,
    }
    (ASSETS / "snapshot-results.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"count": payload["count"], "counts_by_label": payload["counts_by_label"]}))


if __name__ == "__main__":
    main()
