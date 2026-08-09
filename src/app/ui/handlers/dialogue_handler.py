"""Dialog management handler for UI interactions."""

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject

from app.domain.session import SessionId
from app.ui.qt.dialogs import EditAnnotationDialog, ModelChangeWarningDialog

if TYPE_CHECKING:
    from app.ui.uicontroller import UIController


class DialogueHandler(QObject):
    """
    Creates and manages modal dialogs for user interactions.

    Responsibilities:
        - Create and return edit detection dialog with initial values.
        - Create and return model change warning dialog.
        - Pass dialog instances to callers for execution and data retrieval.

    Note:
        Factory pattern: creates dialogs without managing lifecycle.
        Caller is responsible for executing dialog and handling results.
        Centralizes dialog creation logic.
    """

    def __init__(self, controller: UIController):
        super().__init__()
        self._controller = controller
        self._window = controller.window
        self._app = controller.app

    def handle_edit_annotation_dialogue(
        self, initial_label: str, initial_bbox_xyxy: tuple[int, int, int, int]
    ) -> EditAnnotationDialog:
        """
        Create edit detection dialog with initial label and coordinates.
    
        Args:
            initial_label (str): The label text to pre-populate.
            initial_bbox_xyxy (tuple[int, int, int, int]): Tuple ``(x1, y1, x2, y2)`` of detection coordinates.
    
        Returns:
            EditAnnotationDialog: A ``EditAnnotationDialog`` instance ready to execute. Caller must call ``.exec()`` and then ``.get_annotation_data()`` to retrieve results.
        """
        dlg = EditAnnotationDialog(
            self._window, initial_label=initial_label, initial_bbox_xyxy=initial_bbox_xyxy
        )
        return dlg

    def handle_model_change_warning_dialogue(self, s_id: SessionId) -> ModelChangeWarningDialog:
        """
        Create model change warning dialog for the session.
    
        Args:
            s_id (SessionId): Session ID (for context, if needed).
    
        Returns:
            ModelChangeWarningDialog: A ``ModelChangeWarningDialog`` instance ready to execute. Caller must call ``.exec()`` and then ``.get_results()`` to retrieve ``(keep_manual, dont_ask_again)`` tuple.
        """
        dlg = ModelChangeWarningDialog(self._window)
        return dlg
