"""Compatibility seeding shared by editable-layer reads and track mutations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain import VideoDataLayer, new_passes_filter
from app.shared.logging_cfg import get_logger

if TYPE_CHECKING:
    from app.infrastructure.session.session import Session

logger = get_logger("Application->LayerSeeding")


def seed_layer_frame_from_layer(
    source: VideoDataLayer, target: VideoDataLayer, session: Session, frame_index: int
) -> None:
    """Seed an absent editable frame with filtered clones of its source boxes.

    Args:
        source: Immutable source A or C.
        target: Corresponding editable layer B or D.
        session: Session whose data is read and updated.
        frame_index: Frame to initialize if its source contains boxes.

    Side Effects:
        Acquires the session's reentrant data lock across the check and write.
        Existing target frames, including intentionally empty frames, remain
        untouched. Missing or empty source frames do not create target entries.
    """
    with session.data.data_lock:
        if session.data.has_frame_for_layer_at_frame_index(target, frame_index):
            return
        raw_boxes = session.data.get_boxes_for_layer_at_frame_index_as_list(source, frame_index)
        if not raw_boxes:
            return
        copied = [
            box.clone() for box in raw_boxes if new_passes_filter(target, box, session.state.settings)
        ]
        session.data.overwrite_layer_at_index_with_boxes(target, frame_index, copied)
        logger.trace("Seeded {} boxes into Layer {} frame {}", len(copied), target, frame_index)
