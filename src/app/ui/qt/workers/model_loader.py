"""
Module for model loader; implements the Qt presentation components.

See Also:
    - [`load_detection_model`][app.infrastructure.detection.model.loader.load_detection_model] — loads the selected model
    - [`ModelHandler`][app.ui.handlers.model_handler.ModelHandler] — manages worker lifecycle and UI feedback

Layer: Presentation.
Context: Implements the qt presentation components at this architectural boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


from typing import final, override, TYPE_CHECKING

from PySide6.QtCore import QThread, Signal


from app.shared.logging_cfg import get_logger
if TYPE_CHECKING:
    from PySide6.QtCore import QObject
    from app.domain.session import SessionId


if TYPE_CHECKING:
    from app.application.application import Application


logger = get_logger("UI->ModelLoader")


@final
class ModelLoadWorker(QThread):
    """
    Background worker to load a detection model without freezing the UI.


    Layer: Presentation.
    Context: Supports user interaction and delegates application work through presentation contracts.


    Args:
        app: Application used to apply the loaded model and update affected session layers.
        s_id: Identifier of the session associated with this object.
        model_name: Registered name of the detection model.
        keep_manual: Preserve existing manual annotations when changing the model and refreshing model-generated boxes.
        parent: Optional Qt parent object.
    """

    finished = Signal(object, str)  # s_id, model_name
    failed = Signal(object, str, str)  # s_id, model_name, error_message

    def __init__(
        self,
        app: Application,
        s_id: SessionId,
        model_name: str,
        keep_manual: bool = True,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._app: Application = app
        self._s_id: SessionId = s_id
        self._model_name: str = model_name
        self._keep_manual: bool = keep_manual

    def run(self) -> None:
        """
        Load the requested model in the worker thread.
"""
        try:
            logger.info(
                "Starting `ModelLoadWorker(QThread)` for session: '{}' with model: '{}'",
                self._s_id.basename,
                self._model_name,
            )
            self._app.set_detection_model(self._s_id, self._model_name, self._keep_manual)
            self.finished.emit(self._s_id, self._model_name)
        except Exception as exc:
            logger.opt(exception=True).error("`ModelLoadWorker->run()` failed !")
            self.failed.emit(self._s_id, self._model_name, str(exc))

    @override
    def __repr__(self) -> str:
        return f"ModelLoadWorker<s_id='{self._s_id}', model_name='{self._model_name}'>"
