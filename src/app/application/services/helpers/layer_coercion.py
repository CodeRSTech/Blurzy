"""Enum coercion workers for Qt QVariant round-trips.

The ``VideoDataLayer`` and ``ImportMode`` enums are both ``str``-based.

Why coercion is necessary
-------------------------
``str``-based enums inherit from ``str``.  When such an object is stored as
``userData`` in a PySide6 ``QComboBox`` via ``addItem(label, userData)`` and later
retrieved via ``currentData()``, Qt's internal ``QVariant`` machinery sees a ``str``
subclass, strips the Python subclass identity, and returns a **bare** ``str`` instead
of the enum member.

This is **not** a signal/slot crossing issue — it happens in a synchronous method call:

    addItem("Layer A", VideoDataLayer.A)   # VideoDataLayer.A stored in QVariant
    currentData()                           # returns "a" (plain str)

Confirmed call chain (observed 2026-07-29):

    ImportExportDialog._init_widgets()
        self._layer_combo.addItem(_LAYER_LABELS[layer], layer)   # enum → QVariant
                                                                  #        ↓ coerced
    ImportExportDialog._build_config()
        layer = self._layer_combo.currentData()   # returns "a" (str), not VideoDataLayer.A
        ImportExportConfig(layer="a", ...)        # str stored in dataclass

    ImportExportHandler._do_export()
        cfg.layer.name                            # AttributeError: 'str' has no .name

    DetectionExportService.export_layer(layer="a")
        layer.value                               # AttributeError (also caught in log):
        # WARNING | DetectionExportService was provided with string literal 'a'

Fix locations
-------------
PRIMARY   — ``ImportExportDialog._build_config()`` calls ``ensure_layer_enum()``
            immediately after ``currentData()`` so the coerced str is re-wrapped
            before it ever leaves the dialog.

SECONDARY — All four import/export services (DetectionImportService,
            DetectionExportService, TrackingImportService, TrackingExportService)
            call ``ensure_layer_enum()`` at their entry points as a safety net
            for any future programmatic callers that bypass the dialog.

TERTIARY  — ``Application.import_layer()`` and ``Application.export_layer()``
            also coerce at the façade boundary.

Observed similarly for ``ImportMode``:

    mode = self._mode_combo.currentData()   # returns "merge_replace" (str)
    mode.display_label                       # AttributeError: 'str' has no attribute 'display_label'

Do NOT store ``str``-based enum members as QComboBox userData without coercing them
back to enums after ``currentData()`` retrieval.  This pattern silently breaks code
that relies on enum attributes/properties (``name``, ``value``, ``display_label``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.services.helpers.import_mode import ImportMode
from app.domain.video.layer import VideoDataLayer

if TYPE_CHECKING:
    pass


def ensure_layer_enum(layer: VideoDataLayer | str) -> VideoDataLayer:
    """
    Safely coerce a layer to a VideoDataLayer enum.

    Args:
        layer: Either a ``VideoDataLayer`` enum or a string (e.g., ``"a"`` or ``"A"``).

    Returns:
        VideoDataLayer: The corresponding enum member.

    Raises:
        ValueError: If the input is neither a valid enum nor a recognised string.

    Note:
        Accepts both lowercase (``"a"``) and uppercase (``"A"``) strings.
        This handles the common case where Qt or serialisation coerces enums to strings.
    """
    if isinstance(layer, VideoDataLayer):
        return layer

    if isinstance(layer, str):
        # Try lowercase value first (e.g. "a" → VideoDataLayer.A)
        try:
            return VideoDataLayer(layer.lower())
        except ValueError:
            pass

        # Try by enum name, case-insensitive (e.g. "A", "LAYER_A")
        for member in VideoDataLayer:
            if member.name.lower() == layer.lower():
                return member

    raise ValueError(
        f"Cannot coerce '{layer}' (type {type(layer).__name__}) to VideoDataLayer. "
        f"Expected a VideoDataLayer enum or a string like 'a', 'A', etc."
    )


def ensure_import_mode(mode: ImportMode | str) -> ImportMode:
    """
    Safely coerce an import mode to an ImportMode enum.

    Args:
        mode: Either an ``ImportMode`` enum or a string (enum value/name).

    Returns:
        ImportMode: The corresponding enum member.

    Raises:
        ValueError: If the input is neither a valid enum nor a recognised string.

    Note:
        Mirrors :func:`ensure_layer_enum` for the same Qt QVariant round-trip issue
        affecting ``str``-based enums passed through ``QComboBox.currentData()``.
    """
    if isinstance(mode, ImportMode):
        return mode

    if isinstance(mode, str):
        # Try enum value first (e.g. "merge_replace")
        try:
            return ImportMode(mode.lower())
        except ValueError:
            pass

        # Try enum name, case-insensitive (e.g. "MERGE_REPLACE")
        for member in ImportMode:
            if member.name.lower() == mode.lower():
                return member

    raise ValueError(
        f"Cannot coerce '{mode}' (type {type(mode).__name__}) to ImportMode. "
        "Expected an ImportMode enum or a string like 'overwrite' / 'MERGE_REPLACE'."
    )


