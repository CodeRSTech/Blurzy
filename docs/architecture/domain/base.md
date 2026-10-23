# Domain base

Source: `src/app/domain/base`

This package owns domain-level shared types and validation exceptions. Its
`ProcessingSettingsKwargs` type describes partial settings updates; the
domain exception marks invalid empty key-derived sets. Bounding-box, frame,
and session identifiers are defined by their owning packages rather than
duplicated here.

Keep a value here only when multiple domain concepts need it and it has no
more-specific owner. See [domain helpers](helpers.md),
[detection values](detection.md), and [session identity](session.md).
