"""Documentation-only tests; no application or pytest dependencies required."""

from __future__ import annotations

import importlib.util
from pathlib import Path, PurePosixPath
import sys
from tempfile import TemporaryDirectory
import unittest

try:
    from mkdocs.commands.build import build
    from mkdocs.config import load_config
    from mkdocs.exceptions import PluginError
    from mkdocs.structure.files import get_files
    import yaml
except ModuleNotFoundError as exc:
    if exc.name not in ("mkdocs", "yaml"):
        raise
    raise unittest.SkipTest("Install requirements-docs.txt to run documentation tests") from exc

for dependency in ("mkdocstrings", "mkdocstrings_handlers"):
    if importlib.util.find_spec(dependency) is None:
        raise unittest.SkipTest("Install requirements-docs.txt to run documentation tests")


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("docs_reference", ROOT / "scripts" / "docs_reference.py")
assert SPEC is not None and SPEC.loader is not None
reference = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = reference
SPEC.loader.exec_module(reference)


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write("src/app/__init__.py", '"""Application package."""\n')
        self.write("docs/reference/index.md", "# Reference\n")
        self.note = "# Package notes\n\nSource: `src/app/`\n\nKeep this prose.\n"
        self.write("docs/reference/app.md", self.note)
        settings = yaml.safe_load((ROOT / "mkdocs.yml").read_text(encoding="utf-8"))
        settings["hooks"] = [str(ROOT / "scripts" / "docs_reference.py")]
        settings["plugins"] = [
            item for item in settings["plugins"] if isinstance(item, dict) and "mkdocstrings" in item
        ]
        settings["nav"] = [{"Reference": [{"Overview": "reference/index.md"}]}]
        settings["extra_css"] = []
        settings["plugins"][0]["mkdocstrings"]["handlers"]["python"]["paths"] = [str(self.root / "src")]
        self.write("mkdocs.yml", yaml.safe_dump(settings))

    def write(self, name, content):
        path = self.root.joinpath(*PurePosixPath(name).parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def modules(self):
        return reference.discover_modules(self.root)

    def config(self):
        return load_config(config_file=str(self.root / "mkdocs.yml"), strict=True)

    def test_module_and_package_index_names_do_not_collide(self):
        self.write("src/app/index.py", "VALUE = 1\n")
        modules = self.modules()
        self.assertEqual(len({module.page for module in modules}), 2)
        self.assertEqual(str(modules[1].page), "reference/api/app/index/index.md")

    def test_collision_is_explicit(self):
        self.write("src/app/item.py", "")
        self.write("src/app/item/__init__.py", "")
        with self.assertRaisesRegex(PluginError, "collision"):
            self.modules()

    def test_empty_source_fails(self):
        (self.root / "src" / "app" / "__init__.py").unlink()
        with self.assertRaisesRegex(PluginError, "No Python modules"):
            self.modules()

    def test_members_include_aliases_but_not_imports_or_private_names(self):
        self.write(
            "src/app/types.py",
            """
from external import Imported
type PublicAlias = tuple[int, str]
VALUE: int = 1
_private = 2
class Example:
    def method(self): pass
if True:
    def conditional(): pass
try:
    def guarded(): pass
except Exception:
    pass
""",
        )
        module = next(module for module in self.modules() if module.name == "app.types")
        self.assertEqual(reference.local_members(module), ["PublicAlias", "VALUE", "Example", "conditional", "guarded"])

    def test_member_exception_is_explicit(self):
        self.write("src/app/private.py", "def _helper(): pass\n")
        module = next(module for module in self.modules() if module.name == "app.private")
        reference.MEMBER_EXCEPTIONS["app.private"] = ("_helper",)
        self.addCleanup(reference.MEMBER_EXCEPTIONS.pop, "app.private")
        self.assertEqual(reference.local_members(module), ["_helper"])

    def test_package_reexports_link_to_defining_module(self):
        self.write("src/app/__init__.py", 'from .model import Model\n__all__ = ["Model"]\n')
        self.write("src/app/model.py", "class Model: pass\n")
        modules = self.modules()
        page = reference.module_page(modules[0], modules, self.root, "https://example.org/repo")
        self.assertIn("members: []", page)
        self.assertIn("`Model`: [app.model](model/index.md)", page)

    def test_navigation_is_deterministic_and_refreshes(self):
        self.write("src/app/z.py", "")
        old = self.write("src/app/a.py", "")
        first = reference.api_navigation(self.modules())
        self.assertEqual(first, reference.api_navigation(self.modules()))
        self.assertEqual(list(first[1]), ["a"])
        old.rename(old.with_name("renamed.py"))
        new = reference.api_navigation(self.modules())
        self.assertNotEqual(first, new)
        self.assertNotIn("app/a/index.md", str(new))
        old.with_name("renamed.py").unlink()
        self.assertNotIn("renamed", str(reference.api_navigation(self.modules())))

    def test_reexport_chains_and_submodule_exports(self):
        self.write(
            "src/app/__init__.py",
            'from .package import Renamed\nfrom . import package\n__all__ = ["Renamed", "package"]\n',
        )
        self.write("src/app/package/__init__.py", 'from .model import Model as Renamed\n__all__ = ["Renamed"]\n')
        self.write("src/app/package/model.py", "class Model: pass\n")
        modules = self.modules()
        page = reference.module_page(modules[0], modules, self.root, "https://example.org/repo")
        self.assertIn("`Renamed`: [app.package.model](package/model/index.md)", page)
        self.assertIn("`package`: [app.package](package/index.md)", page)

    def test_circular_and_external_reexports_are_not_rendered(self):
        self.write(
            "src/app/__init__.py", 'from .cycle import Item\nfrom external import Other\n__all__ = ["Item", "Other"]\n'
        )
        self.write("src/app/cycle.py", "from app import Item\n")
        modules = self.modules()
        page = reference.module_page(modules[0], modules, self.root, "https://example.org/repo")
        self.assertNotIn("## Public re-exports", page)

    def test_notes_remain_unchanged_and_rebuild_links_are_not_duplicated(self):
        config = self.config()
        for _ in range(2):
            files = config.plugins.on_files(get_files(config), config=config)
            content = files.get_file_from_path("reference/app.md").content_string
            self.assertTrue(content.startswith(self.note))
            self.assertEqual(content.count("## API reference"), 1)
            self.assertEqual((self.root / "docs" / "reference" / "app.md").read_text(), self.note)
            self.assertEqual(len(config.nav[0]["Reference"]), 2)
        self.assertFalse((self.root / "docs" / "reference" / "api").exists())

    def test_missing_note_package_is_an_error(self):
        self.write("docs/reference/broken.md", "# Broken\n\nSource: `src/app/missing/`\n")
        config = self.config()
        with self.assertRaisesRegex(PluginError, "missing package"):
            config.plugins.on_files(get_files(config), config=config)

    def test_generated_subtree_is_reserved(self):
        self.write("docs/reference/api/manual.md", "# Collision\n")
        config = self.config()
        with self.assertRaisesRegex(PluginError, "reserved"):
            config.plugins.on_files(get_files(config), config=config)

    def test_generated_pages_have_no_markdown_edit_url(self):
        from types import SimpleNamespace

        page = SimpleNamespace(
            file=SimpleNamespace(src_uri="reference/api/app/index.md"),
            edit_url="https://example.org/nonexistent.md",
        )
        reference.on_page_context({}, page, None, None)
        self.assertIsNone(page.edit_url)

    def test_serve_watches_source_tree(self):
        from unittest.mock import Mock

        server = Mock()
        builder = Mock()
        self.assertIs(reference.on_serve(server, self.config(), builder), server)
        server.watch.assert_called_once_with(str(self.root / "src" / "app"), builder)

    def test_static_rendering_and_source_rebuild(self):
        module = self.write(
            "src/app/example.py",
            '''
"""Example API."""
from PySide6.QtCore import QObject, Signal
raise RuntimeError("Documentation must never import this module")
type Frame = tuple[int, int]
class Worker(QObject):
    ready = Signal(int)
    def __init__(self, count: int = 1): pass
    def request(self, index: int) -> bool: pass
    def _private(self): pass
''',
        )
        build(self.config())
        html_path = self.root / "site" / "docs" / "reference" / "api" / "app" / "example" / "index.html"
        html = html_path.read_text(encoding="utf-8")
        for member in ("Frame", "Worker", "Worker.ready", "Worker.__init__", "Worker.request"):
            self.assertIn(f'id="app.example.{member}"', html)
        self.assertIn("request(index: int) -&gt; bool", html)
        for member in ("QObject", "Signal", "Worker._private", "Worker.deleteLater"):
            self.assertNotIn(f'id="app.example.{member}"', html)
        self.assertNotIn("edit/master/docs/reference/api", html)
        module.write_text(module.read_text().replace("index: int", "frame: str"), encoding="utf-8")
        build(self.config())
        updated = html_path.read_text(encoding="utf-8")
        self.assertIn("request(frame: str) -&gt; bool", updated)
        module.rename(module.with_name("renamed.py"))
        build(self.config())
        self.assertFalse(html_path.exists())
        self.assertTrue(html_path.parent.parent.joinpath("renamed", "index.html").exists())


if __name__ == "__main__":
    unittest.main()
