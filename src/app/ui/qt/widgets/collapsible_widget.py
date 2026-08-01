from __future__ import annotations

from PySide6.QtWidgets import QWidget, QPushButton, QVBoxLayout, QHBoxLayout


class CollapsibleBox(QWidget):
    """
    A custom widget that provides a collapsible panel.
    Clicking the toggle button shows/hides the child widgets.
    """

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title: str = title
        self.is_expanded: bool = True

        # Toggle button acts as the header
        self.toggle_button = QPushButton(f"▼ {self._title}")
        self.toggle_button.setStyleSheet(
            "text-align: left; font-weight: bold; padding: 6px;"
        )
        self.toggle_button.clicked.connect(self.toggle)

        # Content area holds the actual widgets
        self.content_area: QWidget = QWidget()
        self.content_layout: QVBoxLayout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(15, 5, 5, 10)  # Indent slightly

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(2)
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
