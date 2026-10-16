"""Every error ``code`` the API can answer (doc 20), found by reading the source.

``python manage.py error-codes`` writes them to ``mobile/src/i18n/api-error-codes.json``; a mobile
test fails when one has no Spanish or English text, and an API test fails when the file is out of
date.
"""

import ast
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[2]
EXPORT_PATH = API_ROOT.parent / "mobile" / "src" / "i18n" / "api-error-codes.json"
SOURCES = ("apps", "kuulis")
# Answered by the framework or the exception handlers, not by an ``AppError`` in the code.
BUILT_IN = {
    "bad_request",
    "http_404",
    "http_405",
    "http_429",
    "idempotency_in_progress",
    "idempotency_key_invalid",
    "idempotency_key_reused",
    "rate_limited",
    "validation_error",
}
APP_ERROR_BASES = {"AppError"}


def _files() -> list[Path]:
    files: list[Path] = []
    for folder in SOURCES:
        for path in sorted((API_ROOT / folder).rglob("*.py")):
            if "tests" in path.parts or path.name.startswith("test_"):
                continue
            files.append(path)
    return files


def _string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _error_classes(trees: list[ast.Module]) -> set[str]:
    """Names of every class that inherits (directly or not) from AppError."""
    parents: dict[str, set[str]] = {}
    for tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = {
                    b.id if isinstance(b, ast.Name) else getattr(b, "attr", "") for b in node.bases
                }
                parents[node.name] = bases
    found = set(APP_ERROR_BASES)
    changed = True
    while changed:
        changed = False
        for name, bases in parents.items():
            if name not in found and bases & found:
                found.add(name)
                changed = True
    return found


def collect() -> dict[str, list[str]]:
    """``{code: [files that raise it]}``, sorted by code."""
    trees = {path: ast.parse(path.read_text(), str(path)) for path in _files()}
    classes = _error_classes(list(trees.values()))
    codes: dict[str, set[str]] = {code: {"(built-in)"} for code in BUILT_IN}

    def add(code: str | None, path: Path) -> None:
        if code:
            codes.setdefault(code, set()).add(str(path.relative_to(API_ROOT)))

    for path, tree in trees.items():
        for node in ast.walk(tree):
            # class FooError(AppError): code = "foo"
            if isinstance(node, ast.ClassDef) and node.name in classes:
                for stmt in node.body:
                    target = (
                        stmt.targets[0]
                        if isinstance(stmt, ast.Assign)
                        else getattr(stmt, "target", None)
                    )
                    if isinstance(target, ast.Name) and target.id == "code":
                        add(_string(stmt.value), path)
            # raise AppError("...", code="foo") / FooError(code="foo")
            if isinstance(node, ast.Call):
                func = node.func
                name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
                if name in classes:
                    for kw in node.keywords:
                        if kw.arg == "code":
                            add(_string(kw.value), path)
    return {code: sorted(files) for code, files in sorted(codes.items())}


def render() -> str:
    """The JSON file the app's test reads: ``{"codes": {code: [files]}}``."""
    import json

    return json.dumps({"codes": collect()}, indent=2, ensure_ascii=False) + "\n"
