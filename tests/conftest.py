"""Pytest configuration — mock Qt and heavy dependencies in environments where they are
not installed (unit-test runners, CI without a display server, etc.).

This file is loaded by pytest automatically before any test modules are imported.
When heavy packages are NOT installed, lightweight ``MagicMock`` stubs are injected
into ``sys.modules`` so that application modules can still be imported and unit-tested
without the full dependency stack.

Tests that actually exercise Qt objects (e.g. integration tests using ``qtbot``)
require a real PySide6 installation and will be skipped in minimal environments.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Packages (and their submodules) to stub when not available.
# ---------------------------------------------------------------------------
_OPTIONAL_PACKAGES = [
    # Qt / GUI
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtWidgets",
    "PySide6.QtGui",
    "PySide6.QtMultimedia",
    "PySide6.QtOpenGL",
    # Video decoding (PyAV)
    "av",
    "av.container",
    "av.video",
    "av.video.stream",
    # Image / array dependencies
    "cv2",
    "numpy",
    # ML / computer vision
    "ultralytics",
    "torch",
    "torchvision",
    "mtcnn",
    "scipy",
    "scipy.optimize",
    "pandas",
]


def _install_stubs(packages: list) -> None:
    """Inject ``MagicMock`` stubs for packages that are not installed."""
    for mod_name in packages:
        if mod_name in sys.modules:
            continue
        try:
            __import__(mod_name)
        except ImportError:
            sys.modules[mod_name] = MagicMock()


_install_stubs(_OPTIONAL_PACKAGES)

qtcore = sys.modules.get("PySide6.QtCore")
if qtcore is not None:
    qtcore.Slot = lambda *args, **kwargs: (lambda func: func)
