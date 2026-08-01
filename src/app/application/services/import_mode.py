"""Import merge-strategy enum shared by all layer import services."""

from __future__ import annotations

from enum import Enum


class ImportMode(str, Enum):
    """
    Controls how incoming layer data is reconciled with the existing target layer.

    Attributes:
        OVERWRITE: Wipe the entire target layer first, then load every box from the file.
            This is the safest option when the file is the authoritative source.
        MERGE_REPLACE: For every frame index present in the file, replace that frame's
            boxes in the target layer with the imported ones.  Frames that are *not*
            mentioned in the file are left untouched.
        MERGE_IGNORE: Only populate frames that currently have *no* boxes.  Any frame
            that already contains data is skipped silently.
        MERGE_RENAME: Add every box from the file to the target layer.  If an imported
            box has a ``key`` that already exists in the target frame, the box is added
            with a ``"imp-"`` prefix on both ``key`` and ``id`` to avoid collision.

    Note:
        The dialog offers all four modes with human-readable labels.
        The services receive the enum value and apply the corresponding strategy
        via ``_layer_io.apply_import_to_layer()``.
    """

    OVERWRITE = "overwrite"
    MERGE_REPLACE = "merge_replace"
    MERGE_IGNORE = "merge_ignore"
    MERGE_RENAME = "merge_rename"

    # ---------------------------------------------------------------------------
    # Human-readable labels used by the UI combo box
    # ---------------------------------------------------------------------------
    @property
    def display_label(self) -> str:
        return {
            ImportMode.OVERWRITE: "Overwrite (replace entire layer)",
            ImportMode.MERGE_REPLACE: "Merge – Replace existing frames",
            ImportMode.MERGE_IGNORE: "Merge – Ignore existing frames",
            ImportMode.MERGE_RENAME: "Merge – Rename conflicting keys",
        }[self]

