"""Module for frame boxes view model; defines application concepts without UI or infrastructure dependencies.

Layer: Domain.
Context: Defines application concepts without ui or infrastructure dependencies at this architectural boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


from dataclasses import dataclass, field
if TYPE_CHECKING:
    from app.domain.base.dtypes import ListOfBoxes





@dataclass(slots=True)
class FrameBoxesViewModel:
    """
    Collection of boxes for single frame (UI table model).

    Attributes:
        frame_data_boxes (ListOfBoxes): Boxes displayed for one frame.

    Note:
        Wraps the list of `BBoxViewModel` rows shown in the UI Data tab and
        supports multi-select operations such as copy, delete, and edit.


Layer: Domain.
Context: Represents application concepts without UI or infrastructure dependencies.
"""

    frame_data_boxes: ListOfBoxes = field(default_factory=list)
