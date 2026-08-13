## Phase 7: Regression coverage

### Goal

Protect the refactor with tests that cover shared selection, action routing, relabeling, and transform safety.

### Scope

- selection sync tests
- canvas-originated action enablement tests
- delete-on-selection tests
- relabel-selected tests
- transform-safe interaction tests

### Candidate files

- `tests/ui/**`
- `tests/integration/**`
- any targeted application-layer tests needed for batch relabeling

### Dependencies

- depends on `phase_2.md`
- depends on `phase_4.md`
- depends on `phase_5.md`
- should follow `phase_6.md` for marquee coverage

### Exit criteria

- the core box-selection flows have dedicated regression protection
- batch relabeling is covered
- transformed preview interaction is covered

### Update log

```text
[Contributor]: Copilot
[Timestamp]: 2026-08-10T16:49:51.593+05:30
[Type]: planning
[Summary]:
- Created the phase file for regression coverage.

[Decisions]:
- Regression coverage should target the behavior seams introduced by earlier phases, not only happy-path UI clicks.

[Problems]:
- None

[Next Phase Impact]:
- None
```

```text
[Contributor]: Copilot
[Timestamp]: 2026-08-11T11:20:00.000+05:30
[Type]: implementation
[Summary]:
- Added regression coverage for the shared selection seam and viewport-safe helper behavior.
- Remaining regression work should focus on batch action routing and selection-to-action consistency.

[Decisions]:
- Keep regression tests centered on selection state, action routing, and persistence across refreshes.

[Problems]:
- Some runtime UI paths still need manual validation because they depend on live interaction timing.

[Next Phase Impact]:
- Follow-up testing should target delete/duplicate/relabel batch flows.
```
