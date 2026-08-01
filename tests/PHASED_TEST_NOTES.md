"""Explicit adapter wrapping ``DetectionEngine`` to ``DetectionEngineInterface``."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from app.application.interfaces import DetectionEngineInterface

if TYPE_CHECKING:
    from app.domain.detection.result import DetectionResult
    from app.infrastructure.detection.engine.detection_engine import DetectionEngine


class DetectionEngineAdapter(DetectionEngineInterface):
    """
    Explicit adapter that wraps a concrete ``DetectionEngine`` instance and
    exposes the ``DetectionEngineInterface`` contract.

    In normal usage the concrete ``DetectionEngine`` already satisfies
    ``DetectionEngineInterface`` via structural subtyping (``Protocol``), so
    this adapter is not required for runtime correctness.  It exists to:

    - Provide an explicit, named boundary at the infrastructure/application seam.
    - Enable test doubles that replace the real model without subclassing ``DetectionEngine``.
    - Act as the canonical reference implementation of the interface.
    """

    def __init__(self, engine: DetectionEngine) -> None:
        self._engine = engine

    def __repr__(self) -> str:
        return f"<DetectionEngineAdapter wrapping={self._engine!r}>"

    @property
    def m