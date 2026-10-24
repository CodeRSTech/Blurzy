"""
Module for collapsible panel; implements the Qt presentation components.

See Also:
    - [`create_vbox_layout`][app.ui.qt.shared.layout_shortcuts.create_vbox_layout] — builds the panel's content layout
    - [`RightControlPanel`][app.ui.qt.sections.right_panel.RightControlPanel] — embeds collapsible control sections

Layer: Presentation.
Context: Implements the qt presentation components at this architectural boundary.
"""

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


    Layer: Presentation.
    Context: Supports user interaction and delegates application work through presentation contracts.


    Args:
        title: Text displayed in the panel's header.
        parent: Optional Qt parent object.
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
        """
        Invert the expanded state and update the content visibility and header icon.
        """
        self.is_expanded = not self.is_expanded
        self.content_area.setVisible(self.is_expanded)
        icon = "▼" if self.is_expanded else "▶"
        self.toggle_button.setText(f"{icon} {self._title}")

    def add_widget(self, widget: QWidget) -> None:
        """
        Append a widget to the panel's content layout.

        Args:
            widget: Widget to place in the collapsible content area.
        """
        self.content_layout.addWidget(widget)

    def add_layout(self, layout: QVBoxLayout | QHBoxLayout) -> None:
        """
        Append a nested layout to the panel's content layout.

        Args:
            layout: Layout to place in the collapsible content area.
        """
        self.content_layout.addLayout(layout)
