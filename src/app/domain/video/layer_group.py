"""Data tab enumeration for UI tab selection."""

from enum import Enum

class VideoDataLayerGroup(int, Enum):
    """
    Enumeration for the two main data tabs in the UI.

    Note:
        ``DETECTION`` maps to Layer B for user-edited detections and
        ``TRACKING`` maps to Layer D for user-edited tracks. The enum helps route
        operations to the correct service, determine the active data table, and
        control which boxes are shown in the preview container.

    Example:
        if tab == VideoDataLayerGroup.TRACKING:
            tracking_service.delete_tracks(s_id, keys)
        else:
            detection_service.delete_detections(s_id, keys)
    """
    DETECTION = 0
    TRACKING = 1
