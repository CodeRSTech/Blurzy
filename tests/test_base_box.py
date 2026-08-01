"""Tests for BaseBox domain dataclass and DetectionResult inheritance (Phase 5 conformance).

Covers:
  - BaseBox field defaults and instantiation
  - DetectionResult is a subclass of BaseBox (inheritance wiring)
  - BaseBox is exported from the detection package
  - DetectionResult retains its full API (methods, equality, str)
"""

from __future__ import annotations

from app.domain.detection import Box, DetectionResult
from app.domain.detection.box import Box as BaseBoxDirect


# ---------------------------------------------------------------------------
# BaseBox — basic construction and field access
# ---------------------------------------------------------------------------

class TestBaseBox:
    def test_instantiation_with_all_fields(self):
        b = Box(
            item_id="detection-1",
            label="person",
            bbox_xyxy=(10, 20, 100, 200),
            confidence=0.85,
            color_hex="#ff0000",
        )
        assert b.item_id == "detection-1"
        assert b.label == "person"
        assert b.bbox_xyxy == (10, 20, 100, 200)
        assert b.confidence == 0.85
        assert b.color_hex == "#ff0000"

    def test_color_hex_defaults_to_gray(self):
        b = Box(item_id="x", label="car", bbox_xyxy=(0, 0, 1, 1), confidence=0.5)
        assert b.color_hex == "#808080"

    def test_exported_from_annotation_package(self):
        """BaseBox must be importable from the detection package __init__."""
        assert Box is BaseBoxDirect

    def test_slots_do_not_allow_arbitrary_attributes(self):
        b = Box(item_id="x", label="car", bbox_xyxy=(0, 0, 1, 1), confidence=0.5)
        try:
            b.nonexistent = "should_fail"  # type: ignore[attr-defined]
            assert False, "__slots__ should prevent arbitrary attribute assignment"
        except AttributeError:
            pass

    def test_equality_same_values(self):
        b1 = Box(item_id="a", label="cat", bbox_xyxy=(1, 2, 3, 4), confidence=0.7)
        b2 = Box(item_id="a", label="cat", bbox_xyxy=(1, 2, 3, 4), confidence=0.7)
        assert b1 == b2

    def test_equality_different_values(self):
        b1 = Box(item_id="a", label="cat", bbox_xyxy=(1, 2, 3, 4), confidence=0.7)
        b2 = Box(item_id="b", label="cat", bbox_xyxy=(1, 2, 3, 4), confidence=0.7)
        assert b1 != b2


# ---------------------------------------------------------------------------
# DetectionResult — inherits from BaseBox (wiring check)
# ---------------------------------------------------------------------------

class TestDetectionResultExtendsBaseBox:
    def test_detection_result_is_subclass_of_base_box(self):
        assert issubclass(DetectionResult, Box)

    def test_detection_result_instance_is_also_base_box(self):
        d = DetectionResult(
            item_id="yolo-1", label="person", bbox_xyxy=(10, 20, 100, 200), confidence=0.9
        )
        assert isinstance(d, Box)

    def test_inherited_fields_accessible(self):
        d = DetectionResult(
            item_id="yolo-42",
            label="car",
            bbox_xyxy=(5, 10, 50, 80),
            confidence=0.75,
            color_hex="#aabbcc",
        )
        assert d.item_id == "yolo-42"
        assert d.label == "car"
        assert d.bbox_xyxy == (5, 10, 50, 80)
        assert d.confidence == 0.75
        assert d.color_hex == "#aabbcc"

    def test_default_color_hex_inherited(self):
        d = DetectionResult(
            item_id="yolo-1", label="person", bbox_xyxy=(0, 0, 1, 1), confidence=0.5
        )
        assert d.color_hex == "#808080"


# ---------------------------------------------------------------------------
# DetectionResult — backward-compatible API (behavior parity)
# ---------------------------------------------------------------------------

class TestDetectionResultBehaviorParity:
    def _make(self, item_id="yolo-1", label="person", bbox=(100, 200, 300, 400), conf=0.9):
        return DetectionResult(
            item_id=item_id, label=label, bbox_xyxy=bbox, confidence=conf
        )

    def test_equality_same_id_label_bbox(self):
        d1 = self._make()
        d2 = self._make()
        assert d1 == d2

    def test_inequality_different_item_id(self):
        d1 = self._make(item_id="yolo-1")
        d2 = self._make(item_id="yolo-2")
        assert d1 != d2

    def test_inequality_different_label(self):
        d1 = self._make(label="person")
        d2 = self._make(label="car")
        assert d1 != d2

    def test_inequality_different_bbox(self):
        d1 = self._make(bbox=(0, 0, 100, 100))
        d2 = self._make(bbox=(1, 1, 101, 101))
        assert d1 != d2

    def test_str_representation_contains_key_info(self):
        d = self._make()
        s = str(d)
        assert "yolo-1" in s
        assert "person" in s

    def test_eq_with_non_detection_returns_not_implemented(self):
        d = self._make()
        result = d.__eq__("not_a_detection")
        assert result is NotImplemented
