"""AST-based symbol resolution and source extraction.

Resolves dotted symbol names to Python source files and extracts
function, class, and variable definitions via AST parsing.
"""

from __future__ import annotations

import ast
import os
import textwrap
import warnings
from functools import lru_cache
from typing import Optional

# Directories to skip during fallback file search.
_SKIP_DIRS = frozenset({"__pycache__", ".git", ".eggs", "node_modules", ".tox"})


# ---------------------------------------------------------------------------
# Symbol resolution
# ---------------------------------------------------------------------------


def resolve_symbol_file(
    repo_path: str,
    symbol: str,
) -> tuple[Optional[str], Optional[str]]:
    """Map a dotted symbol name to a concrete ``.py`` file path.

    Returns:
        A ``(file_path, remainder)`` tuple where *remainder* is the
        dot-separated portion of *symbol* not consumed by path resolution.
        Returns ``(None, None)`` when resolution fails.
    """
    parts = symbol.split(".")

    search_roots = [repo_path]
    src_path = os.path.join(repo_path, "src")
    if os.path.isdir(src_path):
        search_roots.append(src_path)

    for root in search_roots:
        for i in range(len(parts), 0, -1):
            candidate = os.path.join(root, "/".join(parts[:i]) + ".py")
            if os.path.isfile(candidate):
                remainder = ".".join(parts[i:]) if i < len(parts) else ""
                return candidate, remainder

            candidate_init = os.path.join(root, "/".join(parts[:i]), "__init__.py")
            if os.path.isfile(candidate_init):
                remainder = ".".join(parts[i:]) if i < len(parts) else ""
                return candidate_init, remainder

    # Fallback: match by filename anywhere in the repo.
    target_filename = parts[0] + ".py"
    for dirpath, dirnames, filenames in os.walk(repo_path):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        if target_filename in filenames:
            found = os.path.join(dirpath, target_filename)
            remainder = ".".join(parts[1:]) if len(parts) > 1 else ""
            return found, remainder

    return None, None


# ---------------------------------------------------------------------------
# AST extraction
# ---------------------------------------------------------------------------


@lru_cache(maxsize=None)
def _parse_file(file_path: str) -> tuple[Optional[str], Optional[ast.Module]]:
    """Read and parse a Python source file, returning ``(source, tree)``."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
            source = fh.read()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source)
        return source, tree
    except (SyntaxError, UnicodeDecodeError):
        return None, None


def extract_symbol_from_ast(
    file_path: str,
    symbol_name: str,
    func_mode: str = "full",
    class_mode: str = "full",
) -> Optional[str]:
    """Extract any symbol (function, class, or variable) from *file_path*.

    For ``Class.member``:
      - full mode: returns the full class (member is already inside).
      - sig_doc mode: returns class signatures + full member definition.
    """
    source, tree = _parse_file(file_path)
    if source is None or tree is None:
        return None

    source_lines = source.splitlines()

    if not symbol_name:
        return None

    parts = symbol_name.split(".")
    target_name = parts[0]
    sub_name = parts[1] if len(parts) > 1 else None

    for node in ast.walk(tree):
        # Top-level function
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == target_name and sub_name is None:
                return _format_function(node, source_lines, func_mode)

        # Class
        elif isinstance(node, ast.ClassDef) and node.name == target_name:
            class_src = _format_class(node, source_lines, class_mode)
            if sub_name is None:
                return class_src

            # Class.member: always include class info
            if class_mode == "full":
                # full class already contains everything
                return class_src

            # sig_doc mode: class signatures + full member definition
            member_src = _find_member(node, source_lines, sub_name, func_mode)
            if member_src:
                return class_src + "\n\n" + member_src
            return class_src

    # Module-level variable
    result = _extract_variable(tree, source_lines, target_name)
    if result is not None:
        return result

    # Follow imports: if the symbol is imported from another file, trace it.
    origin = _trace_import(tree, target_name, file_path)
    if origin is not None:
        return extract_symbol_from_ast(origin, symbol_name, func_mode, class_mode)


# -- Formatting helpers -----------------------------------------------------


def _node_source(node: ast.AST, source_lines: list[str]) -> str:
    """Return the dedented source text for an AST node."""
    lines = source_lines[node.lineno - 1 : node.end_lineno]
    return textwrap.dedent("\n".join(lines))


def _format_function(
    node: ast.AST,
    source_lines: list[str],
    mode: str,
) -> Optional[str]:
    if mode == "full":
        return _node_source(node, source_lines)

    if mode == "sig_doc":
        sig_line = source_lines[node.lineno - 1]
        sig_lines = [sig_line]
        idx = node.lineno
        while not sig_line.rstrip().endswith(":") and idx < len(source_lines):
            sig_line = source_lines[idx]
            sig_lines.append(sig_line)
            idx += 1

        result = textwrap.dedent("\n".join(sig_lines))

        docstring = ast.get_docstring(node)
        if docstring:
            result += '\n    """' + docstring + '"""'

        result += "\n    ..."
        return result

    return None


def _format_class(
    node: ast.ClassDef,
    source_lines: list[str],
    mode: str,
) -> Optional[str]:
    if mode == "full":
        return _node_source(node, source_lines)

    if mode == "sig_doc":
        sig_line = source_lines[node.lineno - 1]
        sig_lines = [sig_line]
        idx = node.lineno
        while not sig_line.rstrip().endswith(":") and idx < len(source_lines):
            sig_line = source_lines[idx]
            sig_lines.append(sig_line)
            idx += 1

        result = textwrap.dedent("\n".join(sig_lines))

        docstring = ast.get_docstring(node)
        if docstring:
            result += '\n    """' + docstring + '"""'

        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                member_sig = _format_function(child, source_lines, "sig_doc")
                if member_sig:
                    result += "\n" + textwrap.indent(member_sig, "    ")
            elif isinstance(child, (ast.Assign, ast.AnnAssign)):
                result += "\n    " + _node_source(child, source_lines).strip()

        return result

    return None


def _find_member(
    class_node: ast.ClassDef,
    source_lines: list[str],
    name: str,
    func_mode: str,
) -> Optional[str]:
    """Find a member by name within a class.

    Searches: methods -> class-level assignments -> self.xxx in all methods.
    """
    # 1. Method
    for child in class_node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == name:
            return _format_function(child, source_lines, func_mode)

    # 2. Class-level assignment
    for child in class_node.body:
        if isinstance(child, ast.Assign):
            for t in child.targets:
                if _assign_target_name(t) == name:
                    return _node_source(child, source_lines)
        elif isinstance(child, ast.AnnAssign) and child.target:
            if _assign_target_name(child.target) == name:
                return _node_source(child, source_lines)

    # 3. self.xxx in any method
    for child in class_node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for stmt in ast.walk(child):
                if isinstance(stmt, ast.Assign):
                    for t in stmt.targets:
                        if (
                            isinstance(t, ast.Attribute)
                            and isinstance(t.value, ast.Name)
                            and t.value.id == "self"
                            and t.attr == name
                        ):
                            return _node_source(stmt, source_lines)

    return None


def _extract_variable(
    tree: ast.Module,
    source_lines: list[str],
    target_name: str,
) -> Optional[str]:
    """Extract a variable assignment by name. Walks entire tree to catch
    assignments inside if/try/with blocks."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if _assign_target_name(target) == target_name:
                    return _node_source(node, source_lines)
        elif isinstance(node, ast.AnnAssign) and node.target:
            if _assign_target_name(node.target) == target_name:
                return _node_source(node, source_lines)
    return None


def _trace_import(
    tree: ast.Module,
    name: str,
    current_file: str,
) -> Optional[str]:
    """If *name* is imported in *current_file*, return the source file path."""
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                local = alias.asname or alias.name
                if local == name:
                    # Resolve relative to current file's directory
                    base_dir = os.path.dirname(current_file)
                    module_parts = node.module.split(".")
                    # Try from current dir upwards
                    for depth in range(len(module_parts) + 1):
                        search_dir = base_dir
                        for _ in range(depth):
                            search_dir = os.path.dirname(search_dir)
                        candidate = os.path.join(search_dir, *module_parts) + ".py"
                        if os.path.isfile(candidate):
                            return candidate
                        candidate_init = os.path.join(search_dir, *module_parts, "__init__.py")
                        if os.path.isfile(candidate_init):
                            return candidate_init
    return None


def _assign_target_name(target: ast.AST) -> Optional[str]:
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    return None


# ---------------------------------------------------------------------------
# Module-reference helpers
# ---------------------------------------------------------------------------


def find_used_attrs_on_module(
    target_func_file: str,
    body_position: list[int],
    module_local_name: str,
) -> list[str]:
    """Find ``module.X`` attribute accesses in the target function body."""
    source, tree = _parse_file(target_func_file)
    if source is None or tree is None:
        return []

    body_start, body_end = body_position

    attrs: list[str] = []
    seen: set[str] = set()
    for node in ast.walk(tree):
        if not hasattr(node, "lineno"):
            continue
        if node.lineno < body_start or node.lineno > body_end:
            continue
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == module_local_name and node.attr not in seen:
                seen.add(node.attr)
                attrs.append(node.attr)
    return attrs


def resolve_module_local_name(
    target_func_file: str,
    module_file_path: str,
    dep_symbol: str,
) -> Optional[str]:
    """Determine the local name used to reference the module in imports."""
    source, tree = _parse_file(target_func_file)
    if source is None or tree is None:
        return dep_symbol.split(".")[-1]

    dep_parts = dep_symbol.split(".")
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == dep_symbol:
                    return alias.asname if alias.asname else dep_parts[-1]
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                full = f"{node.module}.{alias.name}" if node.module else alias.name
                if full == dep_symbol:
                    return alias.asname if alias.asname else alias.name
    return dep_parts[-1]
