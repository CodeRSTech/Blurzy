"""Containment-based duplicate suppression for per-frame tracker inputs."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.base.dtypes import ListOfBoxes
    from app.domain.views import BBoxViewModel


def _area(box: BBoxViewModel) -> int:
    """Return non-negative pixel area for one box.

    Args:
        box: Bounding box whose area is measured.

    Returns:
        Pixel area, or zero for a degenerate box.

    Raises:
        None.

    Note:
        Negative coordinate extents are treated as zero-width or zero-height.

    Example:
        pixels = _area(box)
    """
    x1, y1, x2, y2 = box.bbox_xyxy
    return max(0, x2 - x1) * max(0, y2 - y1)


def _intersection_area(box_a: BBoxViewModel, box_b: BBoxViewModel) -> int:
    """Return the intersection area of two axis-aligned boxes.

    Args:
        box_a: First bounding box.
        box_b: Second bounding box.

    Returns:
        Non-negative pixel area of their intersection.

    Raises:
        None.

    Note:
        Edge-touching boxes have zero area of intersection.

    Example:
        overlap = _intersection_area(box_a, box_b)
    """
    ax1, ay1, ax2, ay2 = box_a.bbox_xyxy
    bx1, by1, bx2, by2 = box_b.bbox_xyxy
    return max(0, min(ax2, bx2) - max(ax1, bx1)) * max(
        0, min(ay2, by2) - max(ay1, by1)
    )


def suppress_nested_same_class_boxes(
    boxes: ListOfBoxes,
    iomin_threshold: float = 0.80,
) -> ListOfBoxes:
    """Suppress duplicate same-class boxes mostly contained by a stronger box.

    Args:
        boxes: Detector boxes from one frame.
        iomin_threshold: Minimum intersection-over-minimum-area ratio.

    Returns:
        Cloned boxes with nested duplicates merged into their retained box.

    Raises:
        ValueError: If ``iomin_threshold`` is outside the inclusive range ``0..1``.

    Note:
        Boxes are prioritized by manual origin, confidence, then area. A candidate
        is merged only into a retained same-label box that is at least as large,
        at least as confident, and has sufficient IoMin. For example, in frame 172,
        ``(682, 447, 1573, 2137)`` and the nested torso box
        ``(676, 458, 1539, 1322)`` have IoU near 0.50 but IoMin near 0.99.
        Suppressing the torso box and unioning the bounds yields
        ``(676, 447, 1573, 2137)``, avoiding duplicate tracks without leaving
        pixels of the subject uncovered. The input boxes are never mutated.

    Example:
        filtered = suppress_nested_same_class_boxes(frame_boxes)
    """
    if not 0.0 <= iomin_threshold <= 1.0:
        raise ValueError("iomin_threshold must be between 0 and 1.")

    ordered = sorted(
        boxes,
        key=lambda box: (
            box.is_manual,
            box.confidence if box.confidence is not None else float("-inf"),
            _area(box),
        ),
        reverse=True,
    )
    retained: list[BBoxViewModel] = []

    for candidate in ordered:
        if candidate.is_manual:
            retained.append(candidate.clone())
            continue

        candidate_area = _area(candidate)
        suppressor = None
        if candidate_area > 0:
            for kept in retained:
                if kept.label != candidate.label or _area(kept) < candidate_area:
                    continue
                kept_confidence = kept.confidence if kept.confidence is not None else float("-inf")
                candidate_confidence = (
                    candidate.confidence if candidate.confidence is not None else float("-inf")
                )
                if kept_confidence < candidate_confidence:
                    continue

                smaller_area = min(_area(kept), candidate_area)
                # IoMin measures how completely the smaller region is covered,
                # unlike IoU, whose union denominator penalizes full-body boxes.
                iomin = _intersection_area(kept, candidate) / smaller_area
                # 0.80 requires at least four-fifths of the smaller region to
                # belong to the same object, while tolerating detector edge jitter.
                if iomin >= iomin_threshold:
                    suppressor = kept
                    break

        if suppressor is None:
            retained.append(candidate.clone())
            continue

        # Union coordinates ensure an imperfectly nested sub-box cannot leave
        # an exposed strip; e.g. x=676 expands the keeper's left edge from 682.
        ax1, ay1, ax2, ay2 = suppressor.bbox_xyxy
        bx1, by1, bx2, by2 = candidate.bbox_xyxy
        suppressor.bbox_xyxy = (
            min(ax1, bx1),
            min(ay1, by1),
            max(ax2, bx2),
            max(ay2, by2),
        )

    return retained
