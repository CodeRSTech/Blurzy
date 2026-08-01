from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.base.dtypes import ListOfBoxes


@dataclass(slots=True)
class FrameBoxesViewModel:
    """
    Collection of boxes for single frame (UI table model).

    Attributes:
        frame_data_boxes (ListOfBoxes): Boxes displayed for one frame.

    Note:
        Wraps the list of ``BBoxViewModel`` rows shown in the UI Data tab and
        supports multi-select operations such as copy, delete, and edit.
    """

    frame_data_boxes: ListOfBoxes = field(default_factory=list)
