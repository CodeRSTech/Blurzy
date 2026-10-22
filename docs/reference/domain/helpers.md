# Domain helpers

Source: `src/app/domain/helpers/`

This package contains small domain-level operations: converting non-empty
string iterables to sets, mapping detection results to box view models, and
applying the confidence/label filter used when deriving editable layer data.
These functions centralize rules without owning file I/O or session
orchestration.

File serialization and import merge modes belong to
[Application service helpers](../application/services/helpers.md). Related
types are [detection](detection.md) and [view models](views.md).
