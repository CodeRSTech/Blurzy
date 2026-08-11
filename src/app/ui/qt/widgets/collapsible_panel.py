from __future__ import annotations

from typing import TYPE_CHECKING


from PySide6.QtWidgets import QWidget, QPushButton

from app.ui.qt.shared.layout_shortcuts import create_vbox_layout
if TYPE_CHECKING:
    from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout



class CollapsiblePanel(QWidget):
    """
    A custom widget that provides a collapsible panel.
    Clicking the toggle button shows/hides the child widgets.
    """

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title: str = title
        self.is_expanded: bool = True

        # Toggle button acts as the section header.
        self.toggle_button = QPushButton(f"▼ {self._title}")
        self.toggle_button.setStyleSheet(
            "text-align: left; font-weight: bold; padding: 6px;"
        )
        self.toggle_button.clicked.connect(self.toggle)

        # Content area holds the actual widgets
        self.content_area: QWidget = QWidget()
        self.content_layout: QVBoxLayout = create_vbox_layout(self.content_area, margins=(15, 5, 5, 10))

        main_layout = create_vbox_layout(self, margins=(0, 0, 0, 0), spacing=2)
        main_layout.addWidget(self.toggle_button)
        main_layout.addWidget(self.content_area)

    def toggle(self) -> None:
        self.is_expanded = not self.is_expanded
        self.content_area.setVisible(self.is_expanded)
        icon = "▼" if self.is_expanded else "▶"
        self.toggle_button.setText(f"{icon} {self._title}")

    def add_widget(self, widget: QWidget) -> None:
        self.content_layout.addWidget(widget)

    def add_layout(self, layout: QVBoxLayout | QHBoxLayout) -> None:
        self.content_layout.addLayout(layout)
