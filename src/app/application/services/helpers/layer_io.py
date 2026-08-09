"""Shared JSON/CSV serialisation helpers for BBoxViewModel layer data.

This module is an *internal* utility — it is not exposed through any ``__init__.py``.
Both the detection and tracking import/export services import from here so that
the wire format is defined in exactly one place.

Wire format
-----------
JSON
~~~~
.. code-block:: json

    {
      "meta": {
        "exported_layer": "B",
        "format_version": "1.0",
        "total_frames": 5,
        "total_boxes": 42
      },
      "frames": {
        "0": [
          {
            "id": "yolo-1",
            "source": "Detection",
            "label": "person",
            "bbox_xyxy": [100, 200, 300, 400],
            "color_hex": "#00ff00",
            "confidence": 0.95,
            "key": "detection:yolo-1"
          }
        ]
      }
    }

CSV
~~~
Columns (tab/comma-separated): ``frame_index, id, source, label, x1, y1, x2, y2,
confidence, color_hex, key``

``source`` is stored as its *value* string (e.g. ``"Detection"``) because
:class:`~app.domain.detection.source.BoxSource` is a ``str``-based enum.
``confidence`` is left blank when ``None``.

Design notes
------------
* ``format_version`` in the JSON meta block enables forward-compatible migrations.
* All keys are preserved verbatim on round-trips.  :meth:`apply_import_to_layer`
  handles collision resolution according to the chosen :class:`ImportMode`.
"""

from __future__ import annotations

import csv
import json
import os
from typing import TYPE_CHECKING

from app.domain import BBoxViewModel
from app.domain.detection.source import BoxSource
from app.application.services.helpers.import_mode import ImportMode

if TYPE_CHECKING:
    from app.domain.base.dtypes import ListOfBoxes
    from app.domain.video.layer import VideoDataLayer
    from app.infrastructure.session.session_data_store import SessionDataStore


_FORMAT_VERSION = "1.0"


# ──────────────────────────────────────────────────────────────────────────────
#  Serialisation (export side)
# ──────────────────────────────────────────────────────────────────────────────

def serialize_layer_to_json(
    layer_name_str: str,
    data: dict[int, ListOfBoxes],
    file_path: str,
) -> int:
    """Write ``data`` as a JSON file.  Returns the number of boxes written."""
    frames: dict[str, list[dict]] = {}
    total_boxes = 0

    for frame_index, boxes in sorted(data.items()):
        if not boxes:
            continue
        frames[str(frame_index)] = [_box_to_dict(b) for b in boxes]
        total_boxes += len(boxes)

    payload = {
        "meta": {
            "exported_layer": layer_name_str,
            "format_version": _FORMAT_VERSION,
            "total_frames": len(frames),
            "total_boxes": total_boxes,
        },
        "frames": frames,
    }

    _ensure_parent_dir(file_path)
    with open(file_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)

    return total_boxes


def serialize_layer_to_csv(
    layer_name_str: str,  # noqa: ARG001 — kept for API symmetry with JSON variant
    data: dict[int, ListOfBoxes],
    file_path: str,
) -> int:
    """Write ``data`` as a CSV file.  Returns the number of boxes written."""
    total_boxes = 0
    _ensure_parent_dir(file_path)

    with open(file_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["frame_index", "id", "source", "label",
             "x1", "y1", "x2", "y2",
             "confidence", "color_hex", "key"]
        )
        for frame_index, boxes in sorted(data.items()):
            for box in boxes:
                x1, y1, x2, y2 = box.bbox_xyxy
                writer.writerow([
                    frame_index,
                    box.id,
                    box.source.value,
                    box.label,
                    x1, y1, x2, y2,
                    "" if box.confidence is None else f"{box.confidence:.4f}",
                    box.color_hex,
                    box.key,
                ])
                total_boxes += 1

    return total_boxes


# ──────────────────────────────────────────────────────────────────────────────
#  Deserialisation (import side)
# ──────────────────────────────────────────────────────────────────────────────

def deserialize_layer_from_json(file_path: str) -> dict[int, ListOfBoxes]:
    """Read a JSON file and return ``{frame_index: [BBoxViewModel, ...]}``.

    Note:
        Unknown ``source`` values that are not registered in ``BoxSource`` will
        raise ``ValueError``.  The calling service should catch and surface this
        as a user-friendly error.
    """
    with open(file_path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)

    frames_raw: dict[str, list[dict]] = payload.get("frames", {})
    return {int(k): [_dict_to_box(d) for d in v] for k, v in frames_raw.items()}


def deserialize_layer_from_csv(file_path: str) -> dict[int, ListOfBoxes]:
    """Read a CSV file and return ``{frame_index: [BBoxViewModel, ...]}``.

    Note:
        Rows with an empty ``confidence`` field are loaded with ``confidence=None``.
    """
    result: dict[int, list[BBoxViewModel]] = {}

    with open(file_path, "r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            frame_index = int(row["frame_index"])
            box = BBoxViewModel(
                id=row["id"],
                source=BoxSource(row["source"]),
                label=row["label"],
                bbox_xyxy=(int(row["x1"]), int(row["y1"]), int(row["x2"]), int(row["y2"])),
                color_hex=row["color_hex"],
                confidence=float(row["confidence"]) if row["confidence"] else None,  # type: ignore[arg-type]
                key=row["key"],
            )
            result.setdefault(frame_index, []).append(box)

    return result


# ──────────────────────────────────────────────────────────────────────────────
#  Merge / apply logic
# ──────────────────────────────────────────────────────────────────────────────

def apply_import_to_layer(
    store: SessionDataStore,
    layer: VideoDataLayer,
    incoming: dict[int, ListOfBoxes],
    mode: ImportMode,
) -> int:
    """Apply ``incoming`` data into ``store``'s ``layer`` according to ``mode``.

    Returns:
        int: Total number of boxes written into the layer.

    Note:
        MERGE_RENAME uses a ``"imp-"`` prefix on both ``key`` and ``id`` for
        each box whose key already exists in the target frame.  This makes
        re-imported boxes distinguishable and avoids silent data loss.

        Consider future improvement: expose a configurable rename prefix so
        callers can pass a session-specific or timestamp-based prefix.
    """
    total_imported = 0

    if mode is ImportMode.OVERWRITE:
        # ------------------------------------------------------------------ #
        # Replace the entire layer atomically.                                #
        # ------------------------------------------------------------------ #
        store.overwrite_layer_with_dict_of_boxes(layer, incoming)
        for boxes in incoming.values():
            total_imported += len(boxes)

    elif mode is ImportMode.MERGE_REPLACE:
        # ------------------------------------------------------------------ #
        # Replace only the frames present in the file.                        #
        # ------------------------------------------------------------------ #
        for frame_index, boxes in incoming.items():
            store.overwrite_layer_at_index_with_boxes(layer, frame_index, list(boxes))
            total_imported += len(boxes)

    elif mode is ImportMode.MERGE_IGNORE:
        # ------------------------------------------------------------------ #
        # Skip frames that already contain any boxes.                         #
        # ------------------------------------------------------------------ #
        for frame_index, boxes in incoming.items():
            if not store.has_boxes_for_layer_at_frame_index(layer, frame_index):
                store.overwrite_layer_at_index_with_boxes(layer, frame_index, list(boxes))
                total_imported += len(boxes)

    elif mode is ImportMode.MERGE_RENAME:
        # ------------------------------------------------------------------ #
        # Append all imported boxes; prefix colliding keys to avoid overlap.  #
        # ------------------------------------------------------------------ #
        for frame_index, boxes in incoming.items():
            existing_keys = {
                b.key
                for b in store.get_boxes_for_layer_at_frame_index_as_list(layer, frame_index)
            }
            resolved: list[BBoxViewModel] = []
            for box in boxes:
                if box.key in existing_keys:
                    cloned = box.clone()
                    cloned.key = f"imp-{box.key}"
                    cloned.id = f"imp-{box.id}"
                    resolved.append(cloned)
                else:
                    resolved.append(box.clone())
            store.add_boxes_to_layer_at_frame_index(layer, frame_index, resolved)
            total_imported += len(resolved)

    return total_imported


# ──────────────────────────────────────────────────────────────────────────────
#  Private helpers
# ──────────────────────────────────────────────────────────────────────────────

def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _box_to_dict(box: BBoxViewModel) -> dict:
    return {
        "id": box.id,
        "source": box.source.value,
        "label": box.label,
        "bbox_xyxy": list(box.bbox_xyxy),
        "color_hex": box.color_hex,
        "confidence": box.confidence,
        "key": box.key,
    }


def _dict_to_box(d: dict) -> BBoxViewModel:
    return BBoxViewModel(
        id=d["id"],
        source=BoxSource(d["source"]),
        label=d["label"],
        bbox_xyxy=tuple(d["bbox_xyxy"]),  # type: ignore[arg-type]
        color_hex=d["color_hex"],
        confidence=d.get("confidence"),  # type: ignore[arg-type]
        key=d.get("key", ""),
    )

