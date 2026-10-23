# Project persistence

Source: `src/app/infrastructure/project`

`ProjectStore` is the file boundary for versioned project JSON: it serializes
domain project documents on save and validates supported format data on load.
It does not reopen videos or assemble runtime sessions. The Application
project service coordinates those steps and reports sessions that cannot be
restored.

The persisted data shape is documented in [Project domain](../domain/project.md);
the live session container and layer storage are described in
[session infrastructure](session.md). Annotation JSON/CSV import and export
use separate [Application service helpers](../application/services/helpers.md).
