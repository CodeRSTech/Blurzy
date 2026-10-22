"""Shared alpha-mask and Gaussian blur rendering used by preview and export.

See Also:
    - [`UIHandler`][app.ui.handlers.ui_handler.UIHandler] — applies masked blur to the preview frame
    - [`ExportService`][app.application.services.export_service.ExportService] — uses the same blur operation when exporting

Layer: Shared utilities.
Context: Provides reusable cross-layer helpers without owning application workflow state.
"""

from __future__ import annotations

import cv2
import numpy as np
from collections.abc import Sequence
from typing import TYPE_CHECKING

from app.shared.logging_cfg import get_logger

if TYPE_CHECKING:
    from app.domain.views import BBoxViewModel

logger = get_logger("Shared->Masked Blur")

_FEATHER_RADIUS = 10


def _clipped_boxes(
    frame_shape: tuple[int, ...],
    boxes: Sequence[BBoxViewModel],
) -> list[tuple[int, int, int, int]]:
    """Return valid box coordinates clipped to the frame bounds.

    Args:
        frame_shape: Image shape beginning with `(height, width)`.
        boxes: Boxes to clip.

    Returns:
        Non-empty coordinates clipped to the image.

    Note:
        Offscreen and degenerate boxes are omitted and logged at trace level.

    Example:
        clipped = _clipped_boxes(frame.shape, boxes)
    """
    height, width = frame_shape[:2]
    clipped = []
    for item in boxes:
        x1, y1, x2, y2 = item.bbox_xyxy
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(width, x2), min(height, y2)
        if x2 > x1 and y2 > y1:
            clipped.append((x1, y1, x2, y2))
        else:
            logger.trace("Skipping empty or offscreen blur box: {}", item.bbox_xyxy)
    return clipped


def _roi_alpha_mask(
    roi_shape: tuple[int, int],
    boxes: list[tuple[int, int, int, int]],
    roi_origin: tuple[int, int],
    feather_radius: int,
) -> np.ndarray:
    """Create the feather alpha values for a padded region of interest.

    Args:
        roi_shape: Region height and width.
        boxes: Absolute coordinates of clipped frame boxes.
        roi_origin: Absolute top-left coordinate of the region.
        feather_radius: Number of pixels over which alpha reaches zero.

    Returns:
        Float alpha values with shape `roi_shape`.

    Note:
        The distance transform expands the union mask smoothly beyond box edges.

    Example:
        alpha = _roi_alpha_mask((80, 80), boxes, (0, 0), 10)
    """
    roi_height, roi_width = roi_shape
    mask = np.ones((roi_height, roi_width), dtype=np.uint8)
    origin_x, origin_y = roi_origin
    for x1, y1, x2, y2 in boxes:
        mask[y1 - origin_y:y2 - origin_y, x1 - origin_x:x2 - origin_x] = 0

    distance = cv2.distanceTransform(mask, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    # Convert distance to a 0..1 ramp: an edge pixel is fully masked and pixels
    # ten pixels out reach zero, matching the export's chosen feather radius.
    alpha = np.clip(1.0 - distance / feather_radius, 0.0, 1.0)
    # Smoothstep removes a visible linear ramp seam while retaining the same radius.
    return alpha * alpha * (3.0 - 2.0 * alpha)


def compute_blur_alpha_mask(
    frame_shape: tuple[int, ...],
    boxes: Sequence[BBoxViewModel],
    feather_radius: int = _FEATHER_RADIUS,
) -> np.ndarray:
    r"""Compute the combined interior-plus-outward-feather alpha mask.

    Args:
        frame_shape: Image shape beginning with `(height, width)`.
        boxes: Bounding boxes whose interiors will be blurred.
        feather_radius: Outward feather distance in pixels.

    Returns:
        A float32 alpha mask of shape `(height, width)` with values from 0 to 1.

    Raises:
        ValueError: If the frame shape or feather radius is invalid.

    Note:
        Distance transform measures each outside pixel's distance to the union of
        box interiors. Alpha reaches zero at `feather_radius`; with the default
        value, the preview footprint includes the same 10-pixel outward zone as
        exported blur.

        For outside distance $d$ and feather radius $r$, the mask uses

        $$
        u = \operatorname{clip}\!\left(1-\frac{d}{r},0,1\right),\qquad
        \alpha = \operatorname{smoothstep}(u)=u^2(3-2u).
        $$

        Box interiors have $\alpha=1$; alpha reaches zero at or beyond the
        feather radius.

    Example:
        mask = compute_blur_alpha_mask(frame.shape, frame_boxes)
    """
    if len(frame_shape) < 2 or frame_shape[0] <= 0 or frame_shape[1] <= 0:
        raise ValueError("frame_shape must contain positive height and width.")
    if feather_radius <= 0:
        raise ValueError("feather_radius must be positive.")
    height, width = frame_shape[:2]
    clipped = _clipped_boxes(frame_shape, boxes)
    result = np.zeros((height, width), dtype=np.float32)
    if not clipped:
        return result

    min_x = max(0, min(box[0] for box in clipped) - feather_radius)
    min_y = max(0, min(box[1] for box in clipped) - feather_radius)
    max_x = min(width, max(box[2] for box in clipped) + feather_radius)
    max_y = min(height, max(box[3] for box in clipped) + feather_radius)
    alpha = _roi_alpha_mask(
        (max_y - min_y, max_x - min_x),
        clipped,
        (min_x, min_y),
        feather_radius,
    )
    result[min_y:max_y, min_x:max_x] = alpha
    return result


def apply_masked_blur(
    frame: np.ndarray,
    boxes: Sequence[BBoxViewModel],
    strength: float,
    feather_radius: int = _FEATHER_RADIUS,
) -> np.ndarray:
    r"""Blur the union of box interiors with a smooth outward alpha feather.

    Args:
        frame: RGB or BGR image to process.
        boxes: Bounding boxes to blur.
        strength: Requested Gaussian kernel width; converted to an odd width of at least three pixels.
        feather_radius: Outward feather distance in pixels.

    Returns:
        The processed frame. The input frame is blurred in place.

    Raises:
        ValueError: If `strength` or `feather_radius` is invalid.

    Note:
        Processing is limited to a padded region of interest; padding includes
        both feather distance and Gaussian context to avoid seams at ROI edges.
        The non-negative strength is truncated to an integer, changed to the
        next odd width when even, and clamped to at least three pixels; call
        this width $k$. OpenCV infers the Gaussian standard deviation from $k$
        because `GaussianBlur` receives `sigmaX=0` (and the default zero
        `sigmaY`). For $h=(k-1)/2$, the ROI blur is the discrete Gaussian
        convolution

        $$
        G(I)_{x,y,c} =
        \sum_{i=-h}^{h}\sum_{j=-h}^{h}
        K_\sigma(i,j)I_{x-i,y-j,c},\qquad
        K_\sigma(i,j)=\frac{1}{Z}
        \exp\!\left(-\frac{i^2+j^2}{2\sigma^2}\right),
        $$

        where $Z$ normalizes the finite kernel to sum to one. For distance
        $d$ outside the union of box interiors and feather radius $r$, the
        feather alpha is

        $$
        u=\operatorname{clip}\!\left(1-\frac{d}{r},0,1\right),\qquad
        \alpha=\operatorname{smoothstep}(u)=u^2(3-2u).
        $$

        Box interiors have $\alpha=1$. Each output channel is

        $$
        O_{x,y,c} =
        \operatorname{astype}_{\operatorname{dtype}(I)}
        \!\left(\operatorname{rint}\!\left(
        (1-\alpha_{x,y})I_{x,y,c}+
        \alpha_{x,y}G(I)_{x,y,c}\right)\right).
        $$

        The input frame is updated in place, and pixels with zero alpha are
        left unchanged.

    Example:
        blurred = apply_masked_blur(frame, tracked_boxes, strength=15.0)
    """
    if strength < 0.0:
        raise ValueError("strength must be non-negative.")
    if feather_radius <= 0:
        raise ValueError("feather_radius must be positive.")
    clipped = _clipped_boxes(frame.shape, boxes)
    if not clipped:
        return frame

    kernel_size = max(3, int(strength) | 1)
    padding = feather_radius + kernel_size // 2
    height, width = frame.shape[:2]
    min_x = max(0, min(box[0] for box in clipped) - padding)
    min_y = max(0, min(box[1] for box in clipped) - padding)
    max_x = min(width, max(box[2] for box in clipped) + padding)
    max_y = min(height, max(box[3] for box in clipped) + padding)

    output = frame
    roi = output[min_y:max_y, min_x:max_x]
    roi_alpha = _roi_alpha_mask(
        (max_y - min_y, max_x - min_x),
        clipped,
        (min_x, min_y),
        feather_radius,
    )[..., None]
    blurred = cv2.GaussianBlur(roi, (kernel_size, kernel_size), 0)
    blended = np.rint(roi * (1.0 - roi_alpha) + blurred * roi_alpha).astype(frame.dtype)
    np.copyto(roi, blended, where=roi_alpha > 0.0)
    return output


def overlay_alpha_mask(
    frame: np.ndarray,
    alpha_mask: np.ndarray,
    color_rgb: tuple[int, int, int] = (255, 48, 48),
    opacity: float = 0.32,
) -> np.ndarray:
    """Draw a semi-transparent RGB highlight for a blur alpha mask.

    Args:
        frame: RGB image to overlay.
        alpha_mask: Float alpha mask with the same height and width.
        color_rgb: Highlight color in RGB channel order.
        opacity: Maximum overlay opacity from 0 to 1.

    Returns:
        A copy of `frame` with the mask highlight.

    Raises:
        ValueError: If dimensions differ or opacity is outside `0..1`.

    Note:
        Mask alpha modulates the maximum color opacity, so the feather remains
        visually gradual instead of appearing as a hard rectangle.

    Example:
        preview = overlay_alpha_mask(frame, mask)
    """
    if alpha_mask.shape != frame.shape[:2]:
        raise ValueError("alpha_mask dimensions must match frame height and width.")
    if not 0.0 <= opacity <= 1.0:
        raise ValueError("opacity must be between 0 and 1.")
    output = frame.copy()
    alpha = (alpha_mask * opacity)[..., None]
    color = np.asarray(color_rgb, dtype=np.float32)
    blended = np.rint(output * (1.0 - alpha) + color * alpha).astype(frame.dtype)
    np.copyto(output, blended, where=alpha > 0.0)
    return output
