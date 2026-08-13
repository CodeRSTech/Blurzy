## Phase 4: Normalize actions around selection

### Goal

Route delete and context-driven operations through selection-aware logic and remove obsolete UI paths.

### Scope

- remove obsolete bottom-panel edit button
- retire broken Delete tool mode
- delete via selection and `Delete` key
- activate selection-aware context actions

### Candidate files

- `src/app/ui/qt/sections/bottom_data_panel.py`
- `src/app/ui/qt/window/window.py`
- `src/app/ui/uicontroller.py`
- `src/app/ui/handlers/annotation_handler.py`
- `src/app/ui/view_state/table_key_filter.py`
- `src/app/ui/qt/widgets/preview/layer_bbox/menu.py`

### Dependencies

- depends on `phase_2.md`
- should consume stable transform behavior from `phase_3.md`

### Exit criteria

- obsolete edit button is removed
- Delete tool mode is retired or unreachable
- delete and context actions operate on the shared selection model

### Update log

```text
[Contributor]: Copilot
[Timestamp]: 2026-08-10T16:49:51.593+05:30
[Type]: planning
[Summary]:
- Created the phase file for action cleanup and routing.

[Decisions]:
- Selection-aware relabeling is handled in Phase 5, not folded into generic delete cleanup.

[Problems]:
- None

[Next Phase Impact]:
- Phase 5 should build on the same action-routing path introduced here.
```

```text
[Contributor]: Copilot
[Timestamp]: 2026-08-10T23:55:00.000+05:30
[Type]: implementation
[Summary]:
- Removed the obsolete edit button from the bottom action row and disabled its use.
- Retired the Delete tool mode from the transport controls by hiding it from the UI.
- Wired Delete key to delete the current shared selection.
- Wired selection actions (select all/none/inverse) and delete through shared selection state.
- Added a relabel-selected button and batch relabel flow for the current selection.

[Decisions]:
- Selection-aware context actions now operate on the shared selection state rather than the last clicked box.
- The shared selection is the single source of truth for delete, relabel, and selection actions.

[Problems]:
- None major; current action routing is now working through the shared selection model.

[Next Phase Impact]:
- Phase 5 can now build on the same relabel and selection wiring without reintroducing UI-specific duplicates.
```
