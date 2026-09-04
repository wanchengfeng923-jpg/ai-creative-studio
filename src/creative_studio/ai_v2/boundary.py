"""AI v2 与旧 AI 的静态边界守卫。"""

from __future__ import annotations

import ast
import re
from pathlib import Path


class AiV2BoundaryViolation(ValueError):
    """v2 源码包含禁止的旧 AI 依赖或入口引用。"""


_SCAN_DIRS = (
    Path("src") / "creative_studio" / "ai_v2",
    Path("static") / "ai-v2",
    Path("config") / "ai_v2",
)


def _forbidden_module_roots() -> tuple[str, ...]:
    package = "creative_studio."
    return (
        package + "ai_" + "creative",
        package + "generation_" + "service",
        package + "carousel_" + "visual",
        package + "static_" + "visual",
        package + "prompt_" + "registry",
        package + "public_" + "projection",
        package + "image_" + "jobs",
        package + "schemas",
        "ai_creative",
        "generation_service",
        "carousel_visual",
        "static_visual",
        "prompt_registry",
        "public_projection",
        "image_jobs",
        "schemas",
    )


def _forbidden_text_patterns() -> tuple[tuple[str, str], ...]:
    old_api = "/api/" + "projects/"
    old_visual_api = "/api/" + "visual-items/"
    return (
        (old_api, "old project API route"),
        (old_visual_api, "old visual item API route"),
        ("generation" + "s", "legacy generation storage"),
        ("visual" + "_items", "legacy visual storage"),
        ("display" + "_frames", "legacy frame storage"),
        ("carousel" + "_operations", "legacy carousel operation storage"),
        ("adoption" + "s", "legacy adoption storage"),
    )


def _iter_files(root: Path) -> tuple[Path, ...]:
    files: list[Path] = []
    for relative_dir in _SCAN_DIRS:
        directory = root / relative_dir
        if not directory.exists():
            continue
        files.extend(path for path in directory.rglob("*") if path.is_file() and path.suffix != ".pyc")
    return tuple(sorted(files))


def _python_import_violations(path: Path, source: str) -> list[str]:
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [f"syntax error at line {exc.lineno}: {exc.msg}"]

    violations: list[str] = []
    forbidden = _forbidden_module_roots()
    for node in ast.walk(tree):
        module_name: str | None = None
        if isinstance(node, ast.Import):
            module_name = node.names[0].name if node.names else None
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            module_name = node.module
        if module_name and any(module_name == root or module_name.startswith(root + ".") for root in forbidden):
            violations.append(f"forbidden import {module_name!r}")
    return violations


def assert_ai_v2_boundary(root: Path) -> None:
    """扫描 v2 目录并在发现旧模块、路由或表名时抛出明确错误。"""

    violations: list[str] = []
    patterns = _forbidden_text_patterns()
    for path in _iter_files(root):
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            violations.append(f"{path.relative_to(root)}: non-UTF-8 source is not allowed")
            continue

        relative_path = path.relative_to(root)
        if path.suffix == ".py":
            for issue in _python_import_violations(path, source):
                violations.append(f"{relative_path}: {issue}")

        for token, description in patterns:
            if token in source:
                line_number = source[: source.index(token)].count("\n") + 1
                source_line = source.splitlines()[line_number - 1].strip()
                violations.append(
                    f"{relative_path}:{line_number}: {description} {token!r} in {source_line!r}"
                )

    if violations:
        raise AiV2BoundaryViolation("AI v2 boundary violations:\n" + "\n".join(sorted(set(violations))))


__all__ = ["AiV2BoundaryViolation", "assert_ai_v2_boundary"]
