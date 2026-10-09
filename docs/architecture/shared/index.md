# Shared utilities

Source: `src/app/shared/`

Shared code provides cross-cutting utilities used by multiple layers,
including logging, exceptions, runtime configuration, image helpers,
annotation serialization, and Qt application metadata.

Shared is a convenience boundary rather than a domain layer. Keep additions
small and broadly reusable; workflow decisions belong in Application and
UI-specific helpers belong in UI.

**Expand this stub with:** utility ownership, logging conventions, and rules
for preventing this package from becoming a catch-all.

