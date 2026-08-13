from __future__ import annotations

from app.ui.qt.shared import layout_shortcuts
from app.ui.qt.shared import qt_class_patches as patches


class _FakeWidget:
    pass


class _FakeBaseLayout:
    def __init__(self, parent=None) -> None:
        self.parent = parent
        self.widgets: list[_FakeWidget] = []
        self.margins: tuple[int, int, int, int] | None = None
        self.spacing: int | None = None

    def addWidget(self, widget: _FakeWidget) -> None:
        self.widgets.append(widget)

    def setContentsMargins(self, left: int, top: int, right: int, bottom: int) -> None:
        self.margins = (left, top, right, bottom)

    def setSpacing(self, spacing: int) -> None:
        self.spacing = spacing


class _FakeHBoxLayout(_FakeBaseLayout):
    pass


class _FakeVBoxLayout(_FakeBaseLayout):
    pass


def _patch_fake_qt(monkeypatch) -> None:
    # Both modules share the same QtWidgets object; patching via either is equivalent.
    monkeypatch.setattr(layout_shortcuts.QtWidgets, "QWidget", _FakeWidget, raising=False)
    monkeypatch.setattr(layout_shortcuts.QtWidgets, "QHBoxLayout", _FakeHBoxLayout, raising=False)
    monkeypatch.setattr(layout_shortcuts.QtWidgets, "QVBoxLayout", _FakeVBoxLayout, raising=False)
    monkeypatch.setattr(patches, "_PATCHED", False)


def test_create_hbox_layout_applies_config_and_adds_widgets(monkeypatch):
    _patch_fake_qt(monkeypatch)

    w1 = _FakeWidget()
    w2 = _FakeWidget()
    layout = layout_shortcuts.create_hbox_layout(
        margins=(1, 2, 3, 4),
        spacing=6,
        widgets=(w1, w2),
    )

    assert layout.margins == (1, 2, 3, 4)
    assert layout.spacing == 6
    assert layout.widgets == [w1, w2]


def test_apply_shortcuts_addwidgets_keeps_widget_order(monkeypatch):
    _patch_fake_qt(monkeypatch)
    patches.apply_qt_ui_shortcuts()

    w1 = _FakeWidget()
    w2 = _FakeWidget()
    w3 = _FakeWidget()
    layout = _FakeVBoxLayout()
    layout.addWidgets([w1, w2, w3])  # type: ignore[attr-defined]

    assert layout.widgets == [w1, w2, w3]


def test_apply_shortcuts_is_idempotent(monkeypatch):
    _patch_fake_qt(monkeypatch)
    patches.apply_qt_ui_shortcuts()
    first_add = _FakeHBoxLayout.addWidgets  # type: ignore[attr-defined]
    first_create_descriptor = _FakeHBoxLayout.__dict__["create"]

    patches.apply_qt_ui_shortcuts()

    assert _FakeHBoxLayout.addWidgets is first_add  # type: ignore[attr-defined]
    assert _FakeHBoxLayout.__dict__["create"] is first_create_descriptor

