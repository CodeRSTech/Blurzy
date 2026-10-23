# Qt shared utilities

Source: `src/app/ui/qt/shared`

Shared Qt utilities provide widget and layout factories, icon tinting,
geometry helpers, reusable layout shortcuts, and debug representations for
Qt objects. They centralize small construction and presentation conventions
used by multiple windows, sections, and widgets; they are not workflow
controllers.

Keep Qt-dependent helpers here only when they are genuinely shared. Widget
behavior belongs in [widgets](widgets.md), top-level composition in the
[window](window.md), and non-Qt helpers in [Shared utilities](../../shared/index.md).
