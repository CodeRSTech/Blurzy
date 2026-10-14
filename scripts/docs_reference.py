"""Generate virtual API pages and navigation without importing the application."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import posixpath
import re

from mkdocs.exceptions import PluginError
from mkdocs.structure.files import File, InclusionLevel


API_ROOT = PurePosixPath("reference/api")
SOURCE_PATTERN = re.compile(r"^Source: `(?P<path>src/app/[^`]*)`", re.MULTILINE)
# Exceptions are keyed by defining module; keep private APIs opt-in.
MEMBER_EXCEPTIONS: dict[str, tuple[str, ...]] = {}
MEMBER_EXCLUSIONS: dict[str, tuple[str, ...]] = {}


def is_type_expression(value: ast.expr | None) -> bool:
    """Recognize conventional assignment-style aliases without evaluating code."""
    if isinstance(value, ast.Subscript):
        return is_type_expression(value.value)
    if isinstance(value, ast.BinOp) and isinstance(value.op, ast.BitOr):
        return is_type_expression(value.left) and is_type_expression(value.right)
    if isinstance(value, ast.Name):
        return value.id[:1].isupper() or value.id in {
            "list",
            "tuple",
            "dict",
            "set",
            "frozenset",
            "str",
            "int",
            "float",
            "bool",
            "bytes",
            "object",
        }
    if isinstance(value, ast.Attribute):
        return value.attr[:1].isupper()
    return isinstance(value, ast.Constant) and value.value is None


def is_api_assignment(name: str, value: ast.expr | None, annotation: ast.expr | None = None) -> bool:
    if name.startswith("_") or name in {"logger", "log"}:
        return False
    if name.isupper():
        return True
    if isinstance(annotation, ast.Name) and annotation.id == "TypeAlias":
        return True
    if isinstance(annotation, ast.Attribute) and annotation.attr == "TypeAlias":
        return True
    return name[:1].isupper() and not isinstance(value, ast.Constant) and is_type_expression(value)


@dataclass(frozen=True)
class Module:
    name: str
    source: Path
    page: PurePosixPath
    is_package: bool


def discover_modules(root: Path) -> list[Module]:
    modules = []
    pages: set[PurePosixPath] = set()
    for source in sorted((root / "src" / "app").rglob("*.py")):
        if "__pycache__" in source.parts:
            continue
        parts = source.relative_to(root / "src").with_suffix("").parts
        is_package = parts[-1] == "__init__"
        name_parts = parts[:-1] if is_package else parts
        # Each module gets its own directory, so index.py cannot collide with __init__.py.
        page = API_ROOT.joinpath(*name_parts, "index.md")
        if page in pages:
            raise PluginError(f"API page collision: {page} ({source})")
        pages.add(page)
        modules.append(Module(".".join(name_parts), source, page, is_package))
    if not modules:
        raise PluginError(f"No Python modules found in {root / 'src' / 'app'}")
    return modules


def local_members(module: Module) -> list[str]:
    """Collect defining-module members, never imported aliases or external APIs."""
    tree = ast.parse(module.source.read_text(encoding="utf-8"), filename=str(module.source))
    names: list[str] = []

    def collect(statements: list[ast.stmt]) -> None:
        for node in statements:
            candidates: list[str] = []
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                candidates = [node.name]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                candidates = [node.target.id] if is_api_assignment(node.target.id, node.value, node.annotation) else []
            elif isinstance(node, ast.TypeAlias):
                candidates = [node.name.id]
            elif isinstance(node, ast.Assign):
                candidates = [
                    target.id
                    for target in node.targets
                    if isinstance(target, ast.Name) and is_api_assignment(target.id, node.value)
                ]
            elif isinstance(node, ast.If):
                collect(node.body)
                collect(node.orelse)
            elif isinstance(node, (ast.Try, ast.TryStar)):
                collect(node.body)
                collect(node.orelse)
                collect(node.finalbody)
                for handler in node.handlers:
                    collect(handler.body)
            names.extend(name for name in candidates if not name.startswith("_"))

    collect(tree.body)
    names.extend(MEMBER_EXCEPTIONS.get(module.name, ()))
    excluded = set(MEMBER_EXCLUSIONS.get(module.name, ()))
    return [name for name in dict.fromkeys(names) if name not in excluded]


def relative_link(origin: PurePosixPath, target: PurePosixPath) -> str:
    return posixpath.relpath(str(target), str(origin.parent))


def registry_assignment(tree: ast.Module, name: str):
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            value = node.value
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            value = node.value
        else:
            continue
        try:
            return ast.literal_eval(value)
        except (TypeError, ValueError) as exc:
            raise PluginError(f"Detection model registry {name} must use literal values") from exc
    raise PluginError(f"Detection model registry is missing {name}")


def detection_model_catalog(root: Path) -> str:
    source = root / "src" / "app" / "infrastructure" / "detection" / "model" / "names.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    registries = (
        ("TorchVision", "TORCH_MODELS"),
        ("Ultralytics YOLO", "ULTRALYTICS_YOLO_MODELS"),
        ("MTCNN", "MTCNN_MODELS"),
    )
    sections = []
    for title, name in registries:
        models = registry_assignment(tree, name)
        if isinstance(models, dict):
            names = list(models)
        elif name == "MTCNN_MODELS" and isinstance(models, (tuple, list)):
            names = models
        else:
            raise PluginError(f"Detection model registry {name} must be a mapping or sequence of names")
        if not all(isinstance(model_name, str) for model_name in names):
            raise PluginError(f"Detection model registry {name} must contain string names")
        sections.append(f"### {title}\n\n" + "".join(f"- `{model_name}`\n" for model_name in names))
    return (
        "\n## Supported models\n\n"
        "This catalog is generated from `app.infrastructure.detection.model.names`.\n\n"
        + "\n".join(sections)
    )


def children(module: Module, modules: list[Module]) -> list[Module]:
    return [child for child in modules if child.name.rpartition(".")[0] == module.name]


def resolve_export(
    module: Module,
    symbol: str,
    modules: dict[str, Module],
    seen: set[tuple[str, str]],
) -> Module | None:
    """Follow internal re-export chains to the defining module, without imports."""
    key = (module.name, symbol)
    if key in seen:
        return None
    seen.add(key)
    if symbol in local_members(module):
        return module
    tree = ast.parse(module.source.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        base = module.name.split(".") if module.is_package else module.name.split(".")[:-1]
        if node.level:
            base = base[: len(base) - node.level + 1]
            imported = ".".join(base + ([node.module] if node.module else []))
        else:
            imported = node.module or ""
        for alias in node.names:
            if (alias.asname or alias.name) != symbol:
                continue
            submodule = modules.get(f"{imported}.{alias.name}")
            if submodule is not None:
                return submodule
            target = modules.get(imported)
            if target is not None:
                return resolve_export(target, alias.name, modules, seen)
    return None


def module_page(module: Module, modules: list[Module], root: Path, repo_url: str) -> str:
    source = module.source.relative_to(root).as_posix()
    title = module.name.rsplit(".", 1)[-1].replace("_", " ")
    text = (
        f'# {title}\n\n<div class="api-module-path"><code>{module.name}</code></div>\n\n'
        f"[View source]({repo_url}/blob/master/{source})\n\n"
    )
    members = local_members(module)
    text += f"::: {module.name}\n    options:\n        members: {members!r}\n"
    if module.name == "app.infrastructure.detection.engine.detection_engine":
        text += detection_model_catalog(root)
    if module.is_package:
        text += "\n## Modules and packages\n\n"
        for child in children(module, modules):
            text += f"- [`{child.name}`]({relative_link(module.page, child.page)})\n"
        # Re-exports link to defining modules; rendering aliases would duplicate anchors.
        tree = ast.parse(module.source.read_text(encoding="utf-8"))
        exports = next(
            (
                ast.literal_eval(node.value)
                for node in tree.body
                if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets)
                and isinstance(node.value, (ast.List, ast.Tuple))
            ),
            (),
        )
        targets = {item.name: item for item in modules}
        links = []
        for public in exports:
            target = resolve_export(module, public, targets, set())
            if target is not None and target != module:
                links.append(f"- `{public}`: [{target.name}]({relative_link(module.page, target.page)})\n")
        if links:
            text += "\n## Public re-exports\n\n" + "".join(links)
    return text


def api_navigation(modules: list[Module], parent: str = "app") -> list:
    module = next(item for item in modules if item.name == parent)
    result: list = [] if parent == "app" else [str(module.page)]
    for child in children(module, modules):
        label = child.name.rsplit(".", 1)[-1]
        descendants = children(child, modules)
        result.append(
            {label: api_navigation(modules, child.name) if child.is_package and descendants else str(child.page)}
        )
    return result


def note_navigation(pages: dict[PurePosixPath, str]) -> list:
    """Build the editorial navigation from page titles and directory structure."""

    def branch(directory: PurePosixPath) -> list:
        result: list = []
        index = directory / "index.md"
        if index in pages:
            result.append(str(index))
        entries = {path.relative_to(directory).parts[0] for path in pages if path.is_relative_to(directory)}
        for entry in sorted(entries):
            path = directory / entry
            if entry == "index.md":
                continue
            if path in pages:
                result.append({pages[path]: str(path)})
            else:
                descendants = branch(path)
                label = entry.replace("_", " ").capitalize()
                result.append(
                    {
                        label: descendants[0]
                        if len(descendants) == 1 and isinstance(descendants[0], str)
                        else descendants
                    }
                )
        return result

    return branch(PurePosixPath("reference"))


def on_files(files, config):
    root = Path(config.config_file_path).resolve().parent
    modules = discover_modules(root)
    targets = {item.source.parent.resolve(): item for item in modules if item.is_package}
    notes: dict[PurePosixPath, str] = {}
    for file in list(files):
        page = PurePosixPath(file.src_uri)
        if page.is_relative_to(API_ROOT):
            raise PluginError(f"{API_ROOT} is reserved for generated pages: {page}")
        if not page.is_relative_to("reference") or not file.is_documentation_page():
            continue
        content = file.content_string
        title = re.search(r"^# (.+)$", content, re.MULTILINE)
        if title is None:
            raise PluginError(f"Reference note lacks a page title: {page}")
        notes[page] = title.group(1)
        match = SOURCE_PATTERN.search(content)
        if match:
            source = root.joinpath(*PurePosixPath(match.group("path")).parts).resolve()
            target = targets.get(source)
            if target is None:
                raise PluginError(f"Reference note {page} points to a missing package: {source}")
            file.content_string = content + (
                f"\n## API reference\n\n[Browse generated `{target.name}` API]({relative_link(page, target.page)}).\n"
            )
    for module in modules:
        files.append(
            File.generated(
                config,
                str(module.page),
                content=module_page(module, modules, root, config.repo_url.rstrip("/")),
            )
        )
    landing = "# API reference\n\nGenerated from source; edit Python docstrings, not these pages.\n\n"
    landing += "[How reference generation works](../../engineering/reference-documentation.md).\n\n"
    app = next(module for module in modules if module.name == "app")
    landing += f"[Application package index]({relative_link(API_ROOT / 'index.md', app.page)})\n\n"
    for module in children(app, modules):
        landing += f"- [{module.name.rsplit('.', 1)[-1]}]({relative_link(API_ROOT / 'index.md', module.page)})\n"
    files.append(File.generated(config, str(API_ROOT / "index.md"), content=landing))
    # Replace rather than append on rebuild; the same config object can be reused by serve.
    reference = next((entry for entry in config.nav if "Reference" in entry), None)
    if reference is None:
        raise PluginError("mkdocs.yml must contain a Reference navigation entry")
    reference["Reference"] = note_navigation(notes)
    api = next((entry for entry in config.nav if "API reference" in entry), None)
    if api is None:
        raise PluginError("mkdocs.yml must contain an API reference navigation entry")
    api["API reference"] = [str(API_ROOT / "index.md"), *api_navigation(modules)]
    # The app wrapper is intentionally absent from the menu, but reachable from the landing page.
    files.get_file_from_path(str(app.page)).inclusion = InclusionLevel.NOT_IN_NAV
    return files


def on_page_context(context, page, config, nav):
    if PurePosixPath(page.file.src_uri).is_relative_to(API_ROOT):
        page.edit_url = None
    return context


def on_serve(server, config, builder):
    root = Path(config.config_file_path).resolve().parent
    server.watch(str(root / "src" / "app"), builder)
    return server
