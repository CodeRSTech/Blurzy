"""Package for workers; implements the Qt presentation components.

See Also:
    - [`ModelLoadWorker`][app.ui.qt.workers.model_loader.ModelLoadWorker] — loads detection models asynchronously
    - [`ModelHandler`][app.ui.handlers.model_handler.ModelHandler] — manages model-worker results

Layer: Presentation.
Context: Implements the qt presentation components at this architectural boundary.
"""

from .model_loader import ModelLoadWorker

__all__ = ["ModelLoadWorker"]