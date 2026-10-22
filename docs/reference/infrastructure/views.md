# Infrastructure view models

Source: `src/app/infrastructure/views/`

This package contains a focused factory that converts runtime `Session`
objects into the session-file-list view model used by the UI. It adapts
infrastructure/session details into a display value; it does not own
interactive selection state or the broader set of domain view-model types.

Other UI-facing value models live in [Domain view models](../domain/views.md),
while transient selection and history live in [UI view state](../ui/view_state.md).
Session ownership and data storage are documented in [session infrastructure](session.md).
