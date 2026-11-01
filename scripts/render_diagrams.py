"""Render architecture D2 sources to themed SVG pairs.

This is an opt-in authoring tool; the documentation build never runs it.
Each ``<name>.d2`` under ``docs/assets/api`` produces ``<name>-light.svg`` and
``<name>-dark.svg`` beside it. Requires the ``d2`` CLI on ``PATH``.

Example:
    ```console
    python scripts/render_diagrams.py
    python scripts/render_diagrams.py docs/assets/api/video
    ```
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets" / "api"
THEMES = {"light": "0", "dark": "200"}


def render(source: Path) -> None:
    """Render one D2 source into its light and dark SVG variants."""
    for name, theme in THEMES.items():
        target = source.with_name(f"{source.stem}-{name}.svg")
        subprocess.run(
            ["d2", "--theme", theme, "--pad", "24", str(source), str(target)],
            check=True,
            capture_output=True,
        )


def main(arguments: list[str]) -> int:
    """Render every D2 file below the given directories (default: all assets)."""
    if shutil.which("d2") is None:
        print("The d2 CLI is required: https://d2lang.com/tour/install", file=sys.stderr)
        return 1
    roots = [Path(argument).resolve() for argument in arguments] or [ASSETS]
    sources = sorted(path for root in roots for path in root.rglob("*.d2"))
    for source in sources:
        render(source)
        print(f"rendered {source.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
