# Project persistence

Source: `src/app/infrastructure/project/`

`ProjectStore` reads and writes project documents as JSON and validates the
supported file format version. The Application project service coordinates
restoring live sessions from those documents.

**Expand this stub with:** format compatibility, corruption handling, and
future migration strategy.

