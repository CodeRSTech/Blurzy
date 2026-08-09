"""DeepSORT strategy adapter.

Simple explanation:
DeepSORT keeps object IDs stable by combining three signals:
1) where the box moved,
2) how much boxes overlap,
3) and visual appearance features.

When a detection is missing for a short time, DeepSORT can still keep a
predicted track alive instead of immediately dropping it.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from app.domain.base.dtypes import ListOfBoxesByFrameIndexAsDict
from app.domain.detection import BoxSource
from app.domain.views import BBoxViewModel
from app.infrastructure.tracking.tracking_strategy import uid_to_color
from app.shared.logging_cfg import get_logger

logger = get_logger("Infrastructure->Tracking->DeepSortStrategy")


def _as_xyxy_int(bbox: Any) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    return int(round(float(x1))), int(round(float(y1))), int(round(float(x2))), int(round(float(y2)))


class DeepSortStrategy:
    """Track objects using DeepSORT while returning app-native view models.

    Simple runtime note:
    This app feeds tracking from box data only (no frame pixels in this layer).
    We run DeepSORT with ``embedder=None`` and supply lightweight embeddings per
    detection so the strategy works without optional embedder packages.
    """

    def __init__(self, min_iou: float = 0.3, min_confidence: float = 0.1, confidence_decay: float = 0.05) -> None:
        try:
            from deep_sort_realtime.deepsort_tracker import DeepSort  # pyright: ignore[reportMissingImports]
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "DeepSORT strategy requires 'deep-sort-realtime'. Install dependencies to use strategy='deepsort'."
            ) from exc

        max_age = max(1, int(round(1.0 / max(confidence_decay, 0.01))))
        self._engine = DeepSort(
            max_age=max_age,
            n_init=1,
            max_iou_distance=min(max(1.0 - min_iou, 0.05), 0.95),
            embedder=None,
        )

    @staticmethod
    def _embed_from_box(item: BBoxViewModel) -> np.ndarray:
        x1, y1, x2, y2 = item.bbox_xyxy
        w = float(max(0, x2 - x1))
        h = float(max(0, y2 - y1))
        cx = float(x1 + x2) / 2.0
        cy = float(y1 + y2) / 2.0
        area = w * h
        conf = float(item.confidence if item.confidence is not None else 1.0)
        label_hash = float(sum(ord(c) for c in item.label) % 97) / 97.0
        vec = np.asarray([cx, cy, w, h, area, conf, label_hash, 1.0], dtype=np.float32)
        norm = float(np.linalg.norm(vec))
        return vec if norm == 0.0 else vec / norm

    def track(
            self,
            source_data: ListOfBoxesByFrameIndexAsDict,
            total_frames: int = 0,
    ) -> ListOfBoxesByFrameIndexAsDict:
        tracked: ListOfBoxesByFrameIndexAsDict = {}
        if not source_data:
            return tracked

        last_seen_detection_index = max(source_data.keys())
        frame_idx = 0
        while frame_idx < total_frames:
            frame_boxes = source_data.get(frame_idx, [])

            # DeepSORT expects [([left, top, width, height], confidence, class_name)].
            raw_detections = []
            embeds: list[np.ndarray] = []
            for item in frame_boxes:
                x1, y1, x2, y2 = item.bbox_xyxy
                raw_detections.append(
                    ([x1, y1, max(0, x2 - x1), max(0, y2 - y1)], float(item.confidence or 1.0), item.label)
                )
                embeds.append(self._embed_from_box(item))

            active_tracks = self._engine.update_tracks(raw_detections, embeds=embeds, frame=None)
            frame_output: list[BBoxViewModel] = []
            for track in active_tracks:
                if hasattr(track, "is_confirmed") and not track.is_confirmed():
                    continue

                uid = int(getattr(track, "track_id"))
                bbox = _as_xyxy_int(track.to_ltrb())
                label_raw = getattr(track, "det_class", "object")
                label = str(label_raw) if label_raw is not None else "object"
                det_conf = getattr(track, "det_conf", 1.0)
                confidence = float(det_conf if det_conf is not None else 1.0)

                frame_output.append(
                    BBoxViewModel(
                        id=f"track-{uid}",
                        source=BoxSource.TRACKING_DEEPSORT,
                        label=label,
                        bbox_xyxy=bbox,
                        color_hex=uid_to_color(uid),
                        confidence=round(confidence, 4),
                        key=f"track:{uid}",
                    )
                )

            has_active = len(frame_output) > 0
            if frame_idx > last_seen_detection_index and not has_active:
                break

            tracked[frame_idx] = frame_output
            frame_idx += 1

        logger.debug("DeepSORT strategy finished. Output frames: {}", len(tracked))
        return tracked
