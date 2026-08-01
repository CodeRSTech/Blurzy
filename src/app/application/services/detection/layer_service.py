"""Detection layer (Layer B) CRUD operations and filtering."""

from __future__ import annotations

from typing import TYPE_CHECKING, final, override

from PySide6.QtCore import QObject

from app.application.adapters import ApplicationAdapter
from app.domain import VideoDataLayer, BoxSource, BBoxViewModel
from app.shared.logging_cfg import get_logger

if TYPE_CHECKING:
    from app.application.application import Application
    from app.infrastructure.session.session import Session
    from app.domain.session.session_id import SessionId
    from app.domain.base.dtypes import BBoxXYXYTuple

logger = get_logger("Application->DetectionLayerService")

@final
class DetectionLayerService(QObject):
    """
    Manages user-editable detection layer (``DataLayer.B``) operations.

    Responsibilities:
        - CRUD operations for ``DataLayer.B`` bounding boxes.
        - Manual detection creation (Create).
        - Copy detections to adjacent frames (Update).
        - Apply confidence and label filtering to detections (Update).
        - Reset detections (revert to ``DataLayer.A``) (Update).
        - Delete detections by key (Delete).

    Note:
        ``DataLayer.A`` — Raw immutable detection output (cannot edit).
        ``DataLayer.B`` — User-editable detections (seeded from A, filtered by settings).
        Filters applied via confidence-threshold and chosen-labels list.
        All user edits are in Layer B only.

        Data Flow:
            Detection Model (YOLO, Torch, etc.) → ``DataLayer.A`` (raw output).
            Apply Filters (confidence, labels) → ``DataLayer.B`` (filtered).
            User Edits (add, delete, move, relabel) on ``DataLayer.B``.
            Export ``DataLayer.B`` to video.
    """

    def __init__(self, app: Application) -> None:
        super().__init__(parent=app)
        # self._app = app
        self._app_adapter = ApplicationAdapter(app)

    @override
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"

    def add_manual_box_to_layer_b_at_current_frame_index(
            self, s_id: SessionId, label: str, bbox_xyxy: BBoxXYXYTuple, color_hex: str = "#00ff00"
    ) -> None:
        # [AUDIT] METHOD NAMING: Name is 50 characters, verbose for routine operation
        # `add_manual_box_to_layer_b_at_current_frame_index` contains redundant context.
        # All manual detection operations in this service already target Layer B, current frame.
        # Recommendation: Shorten to `add_manual_box()` and rely on context.
        # This follows principle of YAGNI (You Aren't Gonna Need It) for method names.
        """
        Add a manually-drawn bounding detection to the current frame in Layer B.
    
        Args:
            s_id (SessionId): Session ID.
            label (str): Object class label (e.g., "person", "car").
            bbox_xyxy (BBoxTuple): Tuple ``(x1, y1, x2, y2)`` in pixel coordinates.
            color_hex (str): Optional color for display (default green).
    
        Note:
            - Creates ``BBoxViewModel`` with confidence=1.0 (user confidence).
            - Assigns unique manual ID via ``next_annotation_id`` counter.
            - Adds to current frame's Layer B.
            - Increments detection ID counter for next manual detection.
        """
        session: Session = self._app_adapter.get_session_by_id(s_id)
        frame_index: int = session.state.playback.current_frame_index

        box = BBoxViewModel(
            id=f"manual-{session.state.next_annotation_id}",
            source=BoxSource.MANUAL,
            label=label,
            bbox_xyxy=bbox_xyxy,
            color_hex=color_hex,
            confidence=1.0,
            key=f"manual:manual-{session.state.next_annotation_id}",
        )
        session.state.next_annotation_id += 1
        session.data.add_box_to_layer_at_frame_index(VideoDataLayer.B, frame_index, box)
