"""Application-wide Qt themes and semantic color tokens."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from app.shared.app_preferences import DEFAULT_THEME, SUPPORTED_THEMES


_THEMES = {
    "light": {
        "window": "#f3f5f8",
        "surface": "#ffffff",
        "surface_raised": "#f8fafc",
        "border": "#d9e0e8",
        "text": "#1e293b",
        "muted": "#64748b",
        "accent": "#e45f44",
        "accent_hover": "#ce4f36",
        "selection": "#dcecff",
        "selection_text": "#17365d",
        "input": "#ffffff",
    },
    "dark": {
        "window": "#171a20",
        "surface": "#20242c",
        "surface_raised": "#282e38",
        "border": "#39414d",
        "text": "#e5eaf1",
        "muted": "#9aa7b7",
        "accent": "#ff8065",
        "accent_hover": "#ff957e",
        "selection": "#394c63",
        "selection_text": "#f1f5f9",
        "input": "#1c2027",
    },
}


def apply_application_theme(application: QApplication, theme: str) -> None:
    """Apply the selected system, light, or dark palette and widget styling.

    Args:
        application: Running Qt application whose palette and stylesheet are updated.
        theme: Theme identifier. Unsupported identifiers use the system theme.

    Side Effects:
        Updates the application palette and stylesheet, refreshing all widgets.
    """
    selected_theme = theme if theme in SUPPORTED_THEMES else DEFAULT_THEME
    if selected_theme == "system":
        palette = application.style().standardPalette()
        colors = {
            "window": palette.color(QPalette.ColorRole.Window).name(),
            "surface": palette.color(QPalette.ColorRole.Base).name(),
            "surface_raised": palette.color(QPalette.ColorRole.Button).name(),
            "border": palette.color(QPalette.ColorRole.Mid).name(),
            "text": palette.color(QPalette.ColorRole.WindowText).name(),
            "muted": palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text).name(),
            "accent": "#e45f44",
            "accent_hover": "#ce4f36",
            "selection": palette.color(QPalette.ColorRole.Highlight).name(),
            "selection_text": palette.color(QPalette.ColorRole.HighlightedText).name(),
            "input": palette.color(QPalette.ColorRole.Base).name(),
        }
    else:
        colors = _THEMES[selected_theme]
        palette = QPalette()
        for role, color_name in (
            (QPalette.ColorRole.Window, colors["window"]),
            (QPalette.ColorRole.Base, colors["input"]),
            (QPalette.ColorRole.AlternateBase, colors["surface_raised"]),
            (QPalette.ColorRole.Button, colors["surface_raised"]),
            (QPalette.ColorRole.ToolTipBase, colors["surface"]),
        ):
            palette.setColor(role, QColor(color_name))
        for role in (
            QPalette.ColorRole.WindowText,
            QPalette.ColorRole.Text,
            QPalette.ColorRole.ButtonText,
            QPalette.ColorRole.ToolTipText,
        ):
            palette.setColor(role, QColor(colors["text"]))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(colors["selection"]))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(colors["selection_text"]))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(colors["muted"]))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(colors["muted"]))

    application.setPalette(palette)
    application.setStyleSheet(
        f"""
        QWidget {{
            color: {colors["text"]};
            font-family: "Segoe UI", "Noto Sans", sans-serif;
            font-size: 10pt;
        }}
        QMainWindow, QDialog, QWidget#centralWidget {{
            background: {colors["window"]};
        }}
        QWidget#controlSection {{
            background: {colors["surface"]};
            border: 1px solid {colors["border"]};
            border-radius: 8px;
        }}
        QPushButton#sectionHeader {{
            color: {colors["text"]};
            background: {colors["surface"]};
            border: 0;
            border-radius: 7px;
            font-weight: 600;
            padding: 9px 10px;
            text-align: left;
        }}
        QPushButton#sectionHeader:hover {{
            background: {colors["surface_raised"]};
        }}
        QFrame#emptyPreviewCard {{
            background: {colors["surface"]};
            border: 1px solid {colors["border"]};
            border-radius: 12px;
        }}
        QLabel#mutedText {{
            color: {colors["muted"]};
        }}
        QMenuBar, QStatusBar {{
            background: {colors["surface"]};
            border: 0;
        }}
        QMenuBar::item {{
            padding: 7px 12px;
            border-radius: 5px;
        }}
        QMenuBar::item:selected, QMenu::item:selected {{
            background: {colors["selection"]};
        }}
        QMenu {{
            background: {colors["surface"]};
            border: 1px solid {colors["border"]};
            padding: 5px;
        }}
        QPushButton {{
            background: {colors["surface_raised"]};
            border: 1px solid {colors["border"]};
            border-radius: 6px;
            padding: 7px 11px;
            min-height: 20px;
        }}
        QPushButton:hover {{
            border-color: {colors["accent"]};
            background: {colors["selection"]};
        }}
        QPushButton:pressed {{
            background: {colors["border"]};
        }}
        QPushButton:disabled {{
            color: {colors["muted"]};
            background: {colors["window"]};
        }}
        QPushButton[emphasis="primary"] {{
            color: #ffffff;
            background: {colors["accent"]};
            border-color: {colors["accent"]};
            font-weight: 600;
        }}
        QPushButton[emphasis="primary"]:hover {{
            background: {colors["accent_hover"]};
        }}
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
            background: {colors["input"]};
            border: 1px solid {colors["border"]};
            border-radius: 5px;
            padding: 5px 7px;
            min-height: 20px;
            selection-background-color: {colors["selection"]};
        }}
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border: 1px solid {colors["accent"]};
        }}
        QComboBox QAbstractItemView {{
            background: {colors["surface"]};
            border: 1px solid {colors["border"]};
            selection-background-color: {colors["selection"]};
        }}
        QTableWidget {{
            background: {colors["surface"]};
            alternate-background-color: {colors["surface_raised"]};
            border: 1px solid {colors["border"]};
            border-radius: 6px;
            gridline-color: {colors["border"]};
            selection-background-color: {colors["selection"]};
        }}
        QHeaderView::section {{
            color: {colors["muted"]};
            background: {colors["surface_raised"]};
            border: 0;
            border-bottom: 1px solid {colors["border"]};
            padding: 7px 8px;
            font-weight: 600;
        }}
        QTabWidget::pane {{
            border: 1px solid {colors["border"]};
            border-radius: 6px;
            top: -1px;
        }}
        QTabBar::tab {{
            color: {colors["muted"]};
            background: transparent;
            border: 0;
            padding: 8px 12px;
            margin-right: 3px;
        }}
        QTabBar::tab:selected {{
            color: {colors["text"]};
            background: {colors["surface"]};
            border-bottom: 2px solid {colors["accent"]};
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 10px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical {{
            background: {colors["border"]};
            border-radius: 4px;
            min-height: 28px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QToolTip {{
            color: {colors["text"]};
            background: {colors["surface"]};
            border: 1px solid {colors["border"]};
            padding: 5px;
        }}
        QSplitter::handle {{
            background: {colors["window"]};
        }}
        """
    )
