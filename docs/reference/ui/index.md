# UI

Source: `src/app/ui/`

The UI layer contains the PySide6 window and widgets, user-action handlers,
controller, adapters, and presentation state. Handlers own Qt signal
orchestration and user-facing error/progress presentation; they delegate
workflow decisions to the Application facade.

## Packages

- [Adapters](adapters.md)
- [Handlers](handlers.md)
- [Interfaces](interfaces.md)
- [Qt components](qt/index.md)
- [View state](view_state.md)

