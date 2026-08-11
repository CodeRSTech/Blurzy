from __future__ import annotations

from typing import TYPE_CHECKING




import PySide6.QtCore as Core
import PySide6.QtGui as Gui
import PySide6.QtWidgets as Widgets

from app.shared.logging_cfg import get_logger
if TYPE_CHECKING:
    from collections.abc import Callable


logger = get_logger("Shared->QtDebugRepr")


def _truncate(text: str, max_len: int = 20) -> str:
    """Helper to keep representations concise."""
    text = text.replace('\n', ' ').strip()
    return f"{text[:max_len - 3]}..." if len(text) > max_len else text


def _safe_repr(obj: Core.QObject, generator: Callable[..., str]) -> str:
    """Safely generates a repr, falling back gracefully if the C++ object is deleted."""
    try:
        return generator(obj)
    except RuntimeError:
        return f"<{obj.__class__.__name__} (C++ object deleted)>"


# --- Specific Generators ---

def _qobject_repr(self: Core.QObject) -> str:
    def gen(o: Core.QObject) -> str:
        name = o.objectName()
        name_str = f" name='{name}'" if name else ""
        return f"<{o.__class__.__name__}{name_str}>"

    return _safe_repr(self, gen)


def _qwidget_repr(self: Widgets.QWidget) -> str:
    def gen(w: Widgets.QWidget) -> str:
        name = w.objectName()
        name_str = f" '{name}'" if name else ""
        geo = w.geometry()
        vis = "Vis" if w.isVisible() else "Hid"
        ena = "Ena" if w.isEnabled() else "Dis"
        return f"<{w.__class__.__name__}{name_str} ({geo.width()}x{geo.height()}) {vis}|{ena}>"

    return _safe_repr(self, gen)


def _qabstractbutton_repr(self: Widgets.QAbstractButton) -> str:
    # Catches QPushButton, QRadioButton, QCheckBox
    def gen(b: Widgets.QAbstractButton) -> str:
        name = b.objectName()
        name_str = f" '{name}'" if name else ""
        text = _truncate(b.text())
        chk = f" checked={b.isChecked()}" if b.isCheckable() else ""
        ena = "Ena" if b.isEnabled() else "Dis"
        return f"<{b.__class__.__name__}{name_str} text='{text}' {ena}{chk}>"

    return _safe_repr(self, gen)


def _qlabel_repr(self: Widgets.QLabel) -> str:
    def gen(l: Widgets.QLabel) -> str:
        name = l.objectName()
        name_str = f" '{name}'" if name else ""
        text = _truncate(l.text(), max_len=30)
        return f"<{l.__class__.__name__}{name_str} text='{text}'>"

    return _safe_repr(self, gen)


def _qcombobox_repr(self: Widgets.QComboBox) -> str:
    def gen(c: Widgets.QComboBox) -> str:
        name = c.objectName()
        name_str = f" '{name}'" if name else ""
        return f"<{c.__class__.__name__}{name_str} items={c.count()} current='{c.currentText()}'>"

    return _safe_repr(self, gen)


def _qslider_repr(self: Widgets.QAbstractSlider) -> str:
    def gen(s: Widgets.QAbstractSlider) -> str:
        name = s.objectName()
        name_str = f" '{name}'" if name else ""
        return f"<{s.__class__.__name__}{name_str} val={s.value()} range=[{s.minimum()}, {s.maximum()}]>"

    return _safe_repr(self, gen)


def _qitemviews_repr(self: Widgets.QAbstractItemView) -> str:
    # Catches QListWidget, QTableWidget, etc.
    def gen(v: Widgets.QAbstractItemView) -> str:
        name = v.objectName()
        name_str = f" '{name}'" if name else ""
        model = v.model()
        rows = model.rowCount() if model else 0
        cols = model.columnCount() if model else 0
        return f"<{v.__class__.__name__}{name_str} size={rows}x{cols}>"

    return _safe_repr(self, gen)


def apply_custom_qt_reprs() -> None:
    """
    Injects custom __repr__ methods into PySide6 base classes.
    Call this EXACTLY ONCE in main.py before QApplication initialization.
    """
    logger.debug("Injecting custom PySide6 __repr__ patches...")

    # 1. Base Fallbacks
    Core.QObject.__repr__ = _qobject_repr
    Widgets.QWidget.__repr__ = _qwidget_repr

    # 2. Buttons & Actions
    Widgets.QAbstractButton.__repr__ = _qabstractbutton_repr
    Gui.QAction.__repr__ = _qabstractbutton_repr  # Duck-types perfectly with button repr

    # 3. Displays & Inputs
    Widgets.QLabel.__repr__ = _qlabel_repr
    Widgets.QComboBox.__repr__ = _qcombobox_repr
    Widgets.QAbstractSlider.__repr__ = _qslider_repr

    # 4. Data Views
    Widgets.QAbstractItemView.__repr__ = _qitemviews_repr

    logger.debug("PySide6 __repr__ patches successfully applied.")