"""Documentation-only tests; no application or pytest dependencies required."""

from __future__ import annotations

import ast
import importlib.util
from html import unescape
from pathlib import Path, PurePosixPath
import re
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
        self.write("docs/architecture/index.md", "# Package notes\n")
        self.write("docs/architecture/overview.md", "# Architecture\n\n[Package notes](index.md)\n")
        self.note = "# Package notes\n\nSource: `src/app/`\n\nKeep this prose.\n"
        self.write("docs/architecture/app.md", self.note)
        settings = yaml.load((ROOT / "mkdocs.yml").read_text(encoding="utf-8"), Loader=yaml.Loader)
        settings["hooks"] = [str(ROOT / "scripts" / "docs_reference.py")]
        settings["plugins"] = [
            item for item in settings["plugins"] if isinstance(item, dict) and "mkdocstrings" in item
        ]
        settings["nav"] = [
            {"Architecture": [{"Overview": "architecture/overview.md"}]},
            {"API reference": ["reference/api/index.md"]},
            {"Development": [{"Reference documentation": "development/reference-documentation.md"}]},
        ]
        self.write("docs/development/reference-documentation.md", "# Reference documentation\n")
        self.write(
            "docs/javascripts/mathjax.js",
            (ROOT / "docs" / "javascripts" / "mathjax.js").read_text(encoding="utf-8"),
        )
        settings["extra_css"] = []
        settings["plugins"][0]["mkdocstrings"]["handlers"]["python"]["paths"] = [str(self.root / "src")]
        self.write("mkdocs.yml", yaml.dump(settings))

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
        self.assertEqual(list(first[0]), ["a"])
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
            content = files.get_file_from_path("architecture/app.md").content_string
            self.assertTrue(content.startswith(self.note))
            self.assertEqual(content.count("## API reference"), 1)
            self.assertEqual((self.root / "docs" / "architecture" / "app.md").read_text(), self.note)
            self.assertEqual(
                config.nav[0]["Architecture"],
                [{"Overview": "architecture/overview.md"}, {"Package notes": "architecture/app.md"}],
            )
            self.assertEqual(config.nav[1]["API reference"], ["reference/api/index.md"])
            self.assertEqual(
                config.nav[2],
                {"Development": [{"Reference documentation": "development/reference-documentation.md"}]},
            )
        self.assertFalse((self.root / "docs" / "reference" / "api").exists())

    def test_missing_note_package_is_an_error(self):
        self.write("docs/architecture/broken.md", "# Broken\n\nSource: `src/app/missing/`\n")
        config = self.config()
        with self.assertRaisesRegex(PluginError, "missing package"):
            config.plugins.on_files(get_files(config), config=config)

    def test_generated_subtree_is_reserved(self):
        self.write("docs/reference/api/manual.md", "# Collision\n")
        config = self.config()
        with self.assertRaisesRegex(PluginError, "reserved"):
            config.plugins.on_files(get_files(config), config=config)

    def test_page_relative_source_mapping_adds_api_link(self):
        note = "# Application\n\nSource: `../../../src/app/`\n"
        self.write("docs/architecture/application/index.md", note)
        config = self.config()
        for _ in range(2):
            files = config.plugins.on_files(get_files(config), config=config)
            content = files.get_file_from_path("architecture/application/index.md").content_string
            self.assertEqual(content.count("## API reference"), 1)
            self.assertIn("../../reference/api/app/index.md", content)
        self.assertEqual((self.root / "docs" / "architecture" / "application" / "index.md").read_text(), note)

    def test_invalid_page_relative_source_mapping_fails(self):
        self.write("docs/architecture/broken.md", "# Broken\n\nSource: `../../src/app/missing/`\n")
        config = self.config()
        with self.assertRaisesRegex(PluginError, "missing package"):
            config.plugins.on_files(get_files(config), config=config)

    def test_missing_required_navigation_is_explicit(self):
        for label in ("Architecture", "API reference"):
            with self.subTest(label=label):
                config = self.config()
                config.nav = [entry for entry in config.nav if label not in entry]
                with self.assertRaisesRegex(PluginError, f"{label} navigation entry"):
                    config.plugins.on_files(get_files(config), config=config)

    def test_architecture_navigation_order_and_discovery(self):
        (self.root / "docs" / "architecture" / "app.md").unlink()
        for package in ("application", "domain", "infrastructure", "shared", "ui", "additional"):
            title = "UI" if package == "ui" else package.capitalize()
            self.write(f"docs/architecture/{package}/index.md", f"# {title}\n")
        self.write("docs/architecture/shared/index.md", "# Shared utilities\n")
        self.write("docs/architecture/ui/widgets/index.md", "# Widgets\n")
        self.write("docs/architecture/ui/widgets/preview.md", "# Preview\n")
        config = self.config()
        files = config.plugins.on_files(get_files(config), config=config)
        self.assertEqual(
            [next(iter(entry)) for entry in config.nav[0]["Architecture"]],
            ["Overview", "UI", "Application", "Infrastructure", "Additional", "Domain", "Shared"],
        )
        self.assertEqual(
            config.nav[0]["Architecture"][1]["UI"],
            [
                "architecture/ui/index.md",
                {
                    "Widgets": [
                        "architecture/ui/widgets/index.md",
                        {"Preview": "architecture/ui/widgets/preview.md"},
                    ]
                },
            ],
        )
        from mkdocs.structure.files import InclusionLevel

        self.assertEqual(files.get_file_from_path("architecture/index.md").inclusion, InclusionLevel.NOT_IN_NAV)
        self.assertIn(
            "../../development/reference-documentation.md",
            files.get_file_from_path("reference/api/index.md").content_string,
        )
        (self.root / "docs" / "architecture" / "additional" / "index.md").unlink()
        config.plugins.on_files(get_files(config), config=config)
        self.assertEqual(
            [next(iter(entry)) for entry in config.nav[0]["Architecture"]],
            ["Overview", "UI", "Application", "Infrastructure", "Domain", "Shared"],
        )

    def test_generated_pages_have_no_markdown_edit_url(self):
        from types import SimpleNamespace

        page = SimpleNamespace(
            file=SimpleNamespace(src_uri="reference/api/app/index.md"),
            edit_url="https://example.org/nonexistent.md",
        )
        reference.on_page_context({}, page, None, None)
        self.assertIsNone(page.edit_url)

    def test_api_asset_references_resolve_for_generated_page_depth(self):
        from types import SimpleNamespace

        self.write(
            "docs/assets/api/tracking/nested-boxes.svg",
            (ROOT / "docs" / "assets" / "api" / "tracking" / "nested-boxes.svg").read_text(encoding="utf-8"),
        )
        config = self.config()

        for page_path, expected_path in (
            ("reference/api/app/index.md", "../../../assets/api/tracking/nested-boxes.svg"),
            (
                "reference/api/app/infrastructure/tracking/index.md",
                "../../../../../assets/api/tracking/nested-boxes.svg",
            ),
        ):
            page = SimpleNamespace(file=SimpleNamespace(src_uri=page_path))
            html = '<img src="api-asset:tracking/nested-boxes.svg" alt="diagram">'
            rendered = reference.on_post_page(html, page, config)
            self.assertIn(f'src="{expected_path}"', rendered)

        page = SimpleNamespace(file=SimpleNamespace(src_uri="reference/api/app/index.md"))
        with self.assertRaisesRegex(PluginError, "does not exist"):
            reference.on_post_page('<img src="api-asset:tracking/missing.svg">', page, config)
        with self.assertRaisesRegex(PluginError, "Invalid API asset"):
            reference.on_post_page('<img src="api-asset:../secret.svg">', page, config)

        self.write("src/app/infrastructure/__init__.py", '"""Infrastructure."""\n')
        self.write("src/app/infrastructure/tracking/__init__.py", '"""Tracking."""\n')
        self.write("src/app/infrastructure/tracking/track_worker.py", "class TrackingWorker: pass\n")
        self.write("src/app/domain/__init__.py", "")
        self.write("src/app/domain/views/__init__.py", "")
        self.write("src/app/domain/views/bounding_box_view_model.py", "class BBoxViewModel: pass\n")
        self.write(
            "src/app/infrastructure/tracking/box_deduplication.py",
            (
                ROOT
                / "src"
                / "app"
                / "infrastructure"
                / "tracking"
                / "box_deduplication.py"
            ).read_text(encoding="utf-8"),
        )
        build(config)
        html_path = (
            self.root
            / "site"
            / "docs"
            / "reference"
            / "api"
            / "app"
            / "infrastructure"
            / "tracking"
            / "box_deduplication"
            / "index.html"
        )
        rendered = html_path.read_text(encoding="utf-8")
        self.assertIn('href="../track_worker/#app.infrastructure.tracking.track_worker.TrackingWorker"', rendered)
        self.assertIn(
            'href="../../../domain/views/bounding_box_view_model/#app.domain.views.bounding_box_view_model.BBoxViewModel"',
            rendered,
        )
        self.assertIn(
            'src="../../../../../../assets/api/tracking/nested-boxes.svg"',
            rendered,
        )
        self.assertIn('class="api-example-image"', rendered)
        self.assertIn("Blue full-body and orange torso boxes", rendered)
        self.assertIn('class="arithmatex"', rendered)
        for formula in (
            r"\frac{740{,}448}{745{,}632}",
            r"\frac{740{,}448}{1{,}510{,}974}",
            "0.993048",
            "0.490047",
            "1{,}515{,}930",
        ):
            self.assertIn(formula, rendered)
        self.assertIn("javascripts/mathjax.js", rendered)
        self.assertIn("mathjax@3.2.2/es5/tex-mml-chtml.js", rendered)
        self.assertTrue(
            (self.root / "site" / "docs" / "assets" / "api" / "tracking" / "nested-boxes.svg").is_file()
        )

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
        self.assertIn("request(index: int) -> bool", unescape(re.sub(r"<[^>]+>", "", html)))
        for member in ("QObject", "Signal", "Worker._private", "Worker.deleteLater"):
            self.assertNotIn(f'id="app.example.{member}"', html)
        self.assertNotIn("edit/master/docs/reference/api", html)
        module.write_text(module.read_text().replace("index: int", "frame: str"), encoding="utf-8")
        build(self.config())
        updated = html_path.read_text(encoding="utf-8")
        self.assertIn("request(frame: str) -> bool", unescape(re.sub(r"<[^>]+>", "", updated)))
        module.rename(module.with_name("renamed.py"))
        build(self.config())
        self.assertFalse(html_path.exists())
        self.assertTrue(html_path.parent.parent.joinpath("renamed", "index.html").exists())

    def test_class_docstring_indentation(self):
        for path in sorted((ROOT / "src" / "app").rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            lines = source.splitlines()
            for node in ast.walk(ast.parse(source)):
                if not isinstance(node, ast.ClassDef) or ast.get_docstring(node, clean=False) is None:
                    continue
                statement = node.body[0]
                with self.subTest(path=str(path.relative_to(ROOT)), class_name=node.name):
                    for line in ast.get_docstring(node, clean=False).splitlines()[1:]:
                        if line.strip():
                            self.assertGreaterEqual(
                                len(line) - len(line.lstrip()),
                                statement.col_offset,
                                "Class docstring continuation lines must retain the body indentation",
                            )
                    closing = lines[statement.end_lineno - 1]
                    if statement.end_lineno > statement.lineno and closing.strip() in ('"""', "'''"):
                        self.assertEqual(len(closing) - len(closing.lstrip()), statement.col_offset)

    def test_real_class_docstrings_render_as_prose_and_sections(self):
        classes = (
            (
                "domain/views/bounding_box_view_model.py",
                "BBoxViewModel",
                "Bounding detection display model",
                "Stored in",
            ),
            (
                "domain/base/dtypes.py",
                "ProcessingSettingsKwargs",
                "Optional keyword fields accepted when updating ProcessingSettings.",
                "Each field is optional",
            ),
        )
        declarations = []
        for path, name, _, _ in classes:
            source = ROOT.joinpath("src", "app", *PurePosixPath(path).parts).read_text(encoding="utf-8")
            node = next(node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ClassDef) and node.name == name)
            declarations.append(ast.get_source_segment(source, node))
        self.write("src/app/example.py", "\n\n".join(declarations) + "\n")
        build(self.config())
        html = (self.root / "site" / "docs" / "reference" / "api" / "app" / "example" / "index.html").read_text(
            encoding="utf-8"
        )
        code_blocks = [
            unescape(re.sub(r"<[^>]+>", "", block))
            for block in re.findall(r"<pre\b[^>]*>.*?</pre>", html, flags=re.DOTALL)
        ]
        for _, name, summary, note in classes:
            with self.subTest(class_name=name):
                self.assertRegex(html, rf"<p>{re.escape(summary)}")
                self.assertIn(note, html)
                for block in code_blocks:
                    self.assertNotIn(summary, block)
                    self.assertNotIn(note, block)
        self.assertIn('class="doc-section-title">Attributes', html)
        self.assertIn('class="admonition-title">Note', html)

    def test_detection_engine_page_renders_model_names_from_literal_registries(self):
        self.write(
            "src/app/infrastructure/detection/engine/detection_engine.py",
            '"""Detection engine."""\nclass DetectionEngine: pass\nraise RuntimeError("Do not import")\n',
        )
        self.write(
            "src/app/infrastructure/detection/model/names.py",
            '''
TORCH_MODELS: dict[str, tuple[str, str]] = {"Torch Example": ("example", "ExampleWeights")}
ULTRALYTICS_YOLO_MODELS: dict[str, str] = {"YOLO Example": "example.pt"}
MTCNN_MODELS = ("MTCNN-Example",)
raise RuntimeError("Do not import")
''',
        )
        for package in (
            "infrastructure",
            "infrastructure/detection",
            "infrastructure/detection/engine",
            "infrastructure/detection/model",
        ):
            self.write(f"src/app/{package}/__init__.py", '"""Test package."""\n')
        build(self.config())
        html_path = (
            self.root
            / "site"
            / "docs"
            / "reference"
            / "api"
            / "app"
            / "infrastructure"
            / "detection"
            / "engine"
            / "detection_engine"
            / "index.html"
        )
        html = html_path.read_text(encoding="utf-8")
        rendered = unescape(re.sub(r"<[^>]+>", " ", html))
        for name in ("Supported models", "Torch Example", "YOLO Example", "MTCNN-Example"):
            self.assertIn(name, rendered)
        for provider in ("TorchVision", "Ultralytics YOLO", "MTCNN"):
            self.assertIn(provider, rendered)

    def test_runtime_wiring_is_excluded_and_aliases_and_constants_remain(self):
        self.write(
            "src/app/policy.py",
            """
from typing import TypeAlias
logger = get_logger("Example")
log: Logger = get_logger("Other")
client = Client()
client_reference = Client
pending = None
cache: dict = {}
DEFAULT_LABEL = "person"
VALID_LOG_LEVELS = frozenset({"DEBUG"})
type Frame = tuple[int, int]
Margins = tuple[int, int, int, int]
OrderedWidgets = list[Widget] | tuple[Widget, ...]
Callback = Callable[[int], None]
Legacy: TypeAlias = tuple[int, str]
runtime = factory()
OMIT_ME = create_singleton()
""",
        )
        module = next(item for item in self.modules() if item.name == "app.policy")
        self.assertEqual(
            reference.local_members(module),
            [
                "DEFAULT_LABEL",
                "VALID_LOG_LEVELS",
                "Frame",
                "Margins",
                "OrderedWidgets",
                "Callback",
                "Legacy",
                "OMIT_ME",
            ],
        )
        reference.MEMBER_EXCEPTIONS[module.name] = ("runtime", "OMIT_ME")
        reference.MEMBER_EXCLUSIONS[module.name] = ("OMIT_ME",)
        self.addCleanup(reference.MEMBER_EXCEPTIONS.pop, module.name)
        self.addCleanup(reference.MEMBER_EXCLUSIONS.pop, module.name)
        members = reference.local_members(module)
        self.assertIn("runtime", members)
        self.assertNotIn("OMIT_ME", members)

    def test_menu_shape_and_index_reachability(self):
        for package in ("application", "domain", "infrastructure", "shared", "ui"):
            self.write(f"src/app/{package}/__init__.py", "")
        self.write("src/app/domain/box.py", "class Box: pass\n")
        self.write("docs/architecture/domain/index.md", "# Domain\n\nSource: `src/app/domain/`\n")
        self.write("docs/architecture/domain/box.md", "# Box\n")
        self.write("docs/architecture/shared/index.md", "# Shared\n\nSource: `src/app/shared/`\n")
        config = self.config()
        files = config.plugins.on_files(get_files(config), config=config)
        api = config.nav[1]["API reference"]
        self.assertEqual(
            [next(iter(item)) for item in api[1:]],
            [
                "application",
                "domain",
                "infrastructure",
                "shared",
                "ui",
            ],
        )
        self.assertEqual(
            api[2]["domain"],
            [
                "reference/api/app/domain/index.md",
                {"box": "reference/api/app/domain/box/index.md"},
            ],
        )
        self.assertIn({"Shared": ["architecture/shared/index.md"]}, config.nav[0]["Architecture"])
        self.assertNotIn("Overview", repr(config.nav[1]))
        for menu in config.nav[:2]:
            self.assertNotIn("'app':", repr(menu))
            self.assertNotIn("'API':", repr(menu))
        from mkdocs.structure.files import InclusionLevel

        self.assertEqual(files.get_file_from_path("reference/api/app/index.md").inclusion, InclusionLevel.NOT_IN_NAV)
        self.assertIn("app/index.md", files.get_file_from_path("reference/api/index.md").content_string)

    def test_representative_example_and_logger_html(self):
        source = (ROOT / "src" / "app" / "infrastructure" / "detection" / "engine" / "detection_engine.py").read_text()
        self.write("src/app/engine.py", source)
        self.write("src/app/infrastructure/__init__.py", "")
        self.write("src/app/infrastructure/detection/__init__.py", "")
        self.write("src/app/infrastructure/detection/model/__init__.py", "")
        self.write("src/app/infrastructure/detection/model/base.py", "class BaseDetectionModel: pass\n")
        self.write("src/app/infrastructure/detection/model/loader.py", "def load_detection_model(): pass\n")
        build(self.config())
        html = (self.root / "site" / "docs" / "reference" / "api" / "app" / "engine" / "index.html").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'href="../infrastructure/detection/model/base/#app.infrastructure.detection.model.base.BaseDetectionModel"',
            html,
        )
        self.assertIn(
            'href="../infrastructure/detection/model/loader/#app.infrastructure.detection.model.loader.load_detection_model"',
            html,
        )
        self.assertNotIn('id="app.engine.logger"', html)
        self.assertNotIn("get_logger(", html)
        self.assertIn('id="app.engine.DetectionEngine.model_name"', html)
        self.assertIn('class="doc doc-label doc-label-property"', html)
        self.assertIn("Switch to a different model at runtime", html)
        self.assertNotRegex(html, r"<h[1-6][^>]*>[^<]*Switch to a different model")
        self.assertIn('class="language-python highlight"', html)
        self.assertIn("<pre>", html)
        self.assertIn('class="c1"', html)
        self.assertIn('class="api-module-path"', html)


if __name__ == "__main__":
    unittest.main()
