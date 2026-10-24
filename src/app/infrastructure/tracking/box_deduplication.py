"""
Containment-based duplicate suppression for per-frame tracker inputs.

See Also:
    - [`TrackingWorker`][app.infrastructure.tracking.track_worker.TrackingWorker] — applies suppression before strategy updates
    - [`BBoxViewModel`][app.domain.views.bounding_box_view_model.BBoxViewModel] — represents candidate boxes

Layer: Infrastructure.
Context: Implements concrete processing and I/O behind application-facing contracts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.base.dtypes import ListOfBoxes
    from app.domain.views import BBoxViewModel


def _area(box: BBoxViewModel) -> int:
    """
    Return non-negative pixel area for one box.

    Args:
        box: Bounding box whose area is measured.

    Returns:
        Pixel area, or zero for a degenerate box.

    Note:
        Negative coordinate extents are treated as zero-width or zero-height.

    Example:
        pixels = _area(box)
    """
    x1, y1, x2, y2 = box.bbox_xyxy
    return max(0, x2 - x1) * max(0, y2 - y1)


def _intersection_area(box_a: BBoxViewModel, box_b: BBoxViewModel) -> int:
    """
    Return the intersection area of two axis-aligned boxes.

    Args:
        box_a: First bounding box.
        box_b: Second bounding box.

    Returns:
        Non-negative pixel area of their intersection.

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
    r"""
    Suppress duplicate same-class boxes mostly contained by a stronger box.

    A stronger box is at least as large and as confident as the candidate;
    manual boxes are prioritized and retained. “Mostly contained” means the
    intersection covers at least `iomin_threshold` of the smaller box.
    Suppressed candidates are merged into the retained box by taking the
    union of their bounds.

    ???+ example "Nested detections example"
        Consider the full body box (682, 447, 1573, 2137) and the nested torso box (676, 458, 1539, 1322)
        that have IoU near 0.50 but IoMin near 0.99.
        Suppressing the torso box and unioning the bounds yields (676, 447, 1573, 2137),
        avoiding duplicate tracks without leaving pixels of the subject uncovered.
        The input boxes are never mutated.

        Assume both detections are non-manual, share a label, and the blue
        full-body box is at least as confident as the orange torso box.

        <img class="api-example-image"
             src="api-asset:tracking/nested-boxes.svg"
             alt="Blue full-body and orange torso boxes; dashed green union extends six pixels left.">

        *Blue full-body and orange torso boxes; dashed green union extends six pixels left.*

        **Coordinates and areas.** Coordinates use $(x_1, y_1, x_2, y_2)$,
        with $y$ increasing downward. Width and height are coordinate
        differences, without adding one pixel.

        | Box | Coordinates | Width by height | Area (${px}^2$) |
        | --- | --- | --- | --- |
        | Full body $B$ | $(682, 447, 1573, 2137)$ | $891 \times 1690$ | $1{,}505{,}790$ |
        | Torso $T$ | $(676, 458, 1539, 1322)$ | $863 \times 864$ | $745{,}632$ |
        | Intersection $I$ or $B \cap T$ | $(682, 458, 1539, 1322)$ | $857 \times 864$ | $740{,}448$ |

        **Intersection and union.** The intersection is
        $(682, 458, 1539, 1322)$:

        $$
        \begin{aligned}
        Area_I &= 857 \times 864 = 740{,}448,\\
        \because \quad X \cup Y &= X + Y - X \cap Y,\\
        \therefore \quad Area_U &= Area_B + Area_T - Area_I,\\
            &= 1{,}505{,}790 + 745{,}632 - 740{,}448\\
            &= 1{,}510{,}974.
        \end{aligned}
        $$

        **Overlap ratios.** IoMin measures coverage of the smaller box;
        IoU divides by the union of both regions:

        $$
        \begin{aligned}
        \operatorname{IoMin}
            &= \frac{Area_I}{\min(Area_B,Area_T)}
             = \frac{740{,}448}{745{,}632}
             \approx 0.993048,\\
        \operatorname{IoU}
            &= \frac{Area_I}{Area_U}
             = \frac{740{,}448}{1{,}510{,}974}
             \approx 0.490047.
        \end{aligned}
        $$

        IoMin exceeds the default threshold $0.80$, although IoU is below
        $0.50$. With the assumptions above, the torso box is merged into
        the larger full-body box rather than retained as a duplicate.

        **Merged bounds.** Taking the minimum lower coordinates and maximum
        upper coordinates yields $(676, 447, 1573, 2137)$. The enclosing
        rectangle is $897 \times 1690$, with area $1{,}515{,}930$.
        This enclosing-rectangle area is not the union area $A_U$: it also
        includes the small gaps between the original regions. The left
        edge expands by $682-676=6$ pixels; all other edges stay unchanged.

    Args:
        boxes: Detector boxes from one frame.
        iomin_threshold: Minimum intersection-over-minimum-area ratio.

    Returns:
        Cloned boxes with nested duplicates merged into their retained box.

    Raises:
        ValueError: If `iomin_threshold` is outside the inclusive range `0..1`.

    Note:
        Boxes are prioritized by manual origin, confidence, then area. A candidate
        is merged only into a retained same-label box that is at least as large,
        at least as confident, and has sufficient IoMin. The input list and its
        boxes are left unchanged.

    !!! example "Usage"
        ```python
        filtered = suppress_nested_same_class_boxes(frame_boxes)
        ```
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
