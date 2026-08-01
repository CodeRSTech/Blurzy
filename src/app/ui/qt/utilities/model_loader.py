from __future__ import annotations

from typing import final, override

from PySide6.QtCore import QObject, QThread, Signal

from app.application.application import Application
from app.domain.session import SessionId
from app.shared.logging_cfg import get_logger

logger = get_logger("UI->ModelLoader")


@final
class ModelLoadWorker(QThread):
    """
    Background worker to load a detection model without freezing the UI.
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
