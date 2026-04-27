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

            # sig_doc / sd_init: class signatures + full member definition
            # (for sd_init, __init__ is already in class_src, but the target
            # member still shown separately for clarity when sub_name matches)
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
    """Return the dedented source text for an AST node, including decorators."""
    start = _node_start_lineno(node) if hasattr(node, "decorator_list") else node.lineno
    lines = source_lines[start - 1 : node.end_lineno]
    return textwrap.dedent("\n".join(lines))


def _is_docstring(stmt: ast.AST) -> bool:
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, str)
    )


def _node_start_lineno(node: ast.AST) -> int:
    """Earliest source line of a function/class, including decorators."""
    decos = getattr(node, "decorator_list", []) or []
    if decos:
        return min(d.lineno for d in decos)
    return node.lineno


def _format_function(
    node: ast.AST,
    source_lines: list[str],
    mode: str,
) -> Optional[str]:
    start_lineno = _node_start_lineno(node)

    if mode == "full":
        # Re-implement _node_source but starting from the decorator line.
        lines = source_lines[start_lineno - 1 : node.end_lineno]
        return textwrap.dedent("\n".join(lines))

    if mode == "sig_doc":
        if not node.body:
            return None
        first_body = node.body[0]

        # Signature: from start (decorator or def) to first body stmt.
        sig_end_excl = first_body.lineno - 1
        sig_lines = source_lines[start_lineno - 1 : sig_end_excl]
        result = textwrap.dedent("\n".join(sig_lines))

        # Docstring: preserve raw source formatting (re-indented to 4 spaces).
        if _is_docstring(first_body):
            doc_lines = source_lines[first_body.lineno - 1 : first_body.end_lineno]
            doc_text = textwrap.dedent("\n".join(doc_lines))
            result += "\n" + textwrap.indent(doc_text, "    ")

        result += "\n    ..."
        return result

    return None


def _format_class(
    node: ast.ClassDef,
    source_lines: list[str],
    mode: str,
) -> Optional[str]:
    # For focused modes, when extracting a whole class (no specific members
    # to focus on), fall back to the corresponding non-focused mode.
    if mode == "full_focused":
        mode = "full"
    elif mode == "sig_doc_focused":
        mode = "sig_doc"
    elif mode == "sd_init_focused":
        mode = "sd_init"

    if mode == "full":
        return _node_source(node, source_lines)

    if mode in ("sig_doc", "sd_init"):
        if not node.body:
            return None
        first_body = node.body[0]

        # Signature: class header up to first body stmt (include decorators,
        # handle multi-line bases).
        start_lineno = _node_start_lineno(node)
        sig_end_excl = first_body.lineno - 1
        sig_lines = source_lines[start_lineno - 1 : sig_end_excl]
        result = textwrap.dedent("\n".join(sig_lines))

        # Docstring (preserve raw formatting).
        body_iter_start = 0
        if _is_docstring(first_body):
            doc_lines = source_lines[first_body.lineno - 1 : first_body.end_lineno]
            doc_text = textwrap.dedent("\n".join(doc_lines))
            result += "\n" + textwrap.indent(doc_text, "    ")
            body_iter_start = 1

        for child in node.body[body_iter_start:]:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # sd_init: __init__ is shown in full, others sig_doc.
                if mode == "sd_init" and child.name == "__init__":
                    member_src = _format_function(child, source_lines, "full")
                else:
                    member_src = _format_function(child, source_lines, "sig_doc")
                if member_src:
                    result += "\n" + textwrap.indent(member_src, "    ")
            elif isinstance(child, (ast.Assign, ast.AnnAssign)):
                result += "\n    " + _node_source(child, source_lines).strip()

        return result

    return None


def extract_class_with_dep_members(
    file_path: str,
    class_name: str,
    dep_members: list[str],
    mode: str,
    redact_member: Optional[str] = None,
) -> Optional[str]:
    """Extract a class focused on specific dep members.

    - mode='sig_doc': class skeleton (all method sigs + class attrs) +
                      each dep method appended as its FULL body.
                      Non-method dep members are skipped (instance attrs are
                      implicit in the skeleton's signatures).
    - mode='full':    full class source. If ``redact_member`` is given,
                      that method's body is replaced with ``...`` to avoid
                      leaking the target answer.
    """
    source, tree = _parse_file(file_path)
    if source is None or tree is None:
        return None
    source_lines = source.splitlines()

    class_node: Optional[ast.ClassDef] = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            class_node = node
            break
    if class_node is None:
        return None

    if mode == "full":
        return _format_class_with_redact(class_node, source_lines, redact_member)

    if mode in ("sig_doc", "sd_init"):
        # Full skeleton (sigs of every member) + dep members appended in full.
        skeleton = _format_class(class_node, source_lines, mode)
        if skeleton is None:
            return None
        parts = [skeleton]
        for name in dep_members:
            if name == redact_member:
                continue
            if mode == "sd_init" and name == "__init__":
                continue  # already shown in full inside the skeleton
            for child in class_node.body:
                if (
                    isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and child.name == name
                ):
                    full = _format_function(child, source_lines, "full")
                    if full:
                        parts.append(full)
                    break
        return "\n\n".join(parts)

    if mode in ("sig_doc_focused", "sd_init_focused", "full_focused"):
        # Class signature with ONLY the dep members rendered inside the class.
        # Instance attrs (like `self.x` set in __init__) are not class-body
        # members — auto-include the method that sets them so the model can
        # see how/where the attr is defined.
        sig_end_excl = class_node.body[0].lineno - 1 if class_node.body else class_node.lineno
        start = _node_start_lineno(class_node)
        sig_lines = source_lines[start - 1 : sig_end_excl]
        result = textwrap.dedent("\n".join(sig_lines))

        # Resolve each dep_member to a class method node.
        # Track whether each method was triggered as a "direct method dep" or
        # as an "instance-attr setter" — setters are always rendered in full
        # so the assignment lines are visible.
        method_to_kind: dict[ast.AST, str] = {}  # node -> 'direct' or 'setter'
        for name in dep_members:
            if name == redact_member:
                continue
            direct = None
            for child in class_node.body:
                if (
                    isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and child.name == name
                ):
                    direct = child
                    break
            if direct is not None:
                if direct not in method_to_kind:
                    method_to_kind[direct] = "direct"
            else:
                setter = _find_instance_attr_setter(class_node, name)
                if setter is not None and setter.name != redact_member:
                    # Promote to 'setter' (full body) only if not already direct.
                    method_to_kind.setdefault(setter, "setter")

        for method_node, kind in method_to_kind.items():
            if kind == "setter":
                member_mode = "full"
            elif mode == "full_focused":
                member_mode = "full"
            elif mode == "sd_init_focused" and method_node.name == "__init__":
                member_mode = "full"
            else:
                member_mode = "sig_doc"
            src = _format_function(method_node, source_lines, member_mode)
            if src:
                result += "\n" + textwrap.indent(src, "    ")

        if not method_to_kind:
            result += "\n    ..."
        return result

    return None


def _format_class_focused(
    node: ast.ClassDef,
    source_lines: list[str],
    dep_members: list[str],
) -> str:
    """For cross-file class.member deps in 'full' mode: class signature line
    only, plus each requested dep member in full body. This avoids pulling
    in huge external class bodies just because one method was referenced.
    """
    sig_end_excl = node.body[0].lineno - 1 if node.body else node.lineno
    start = _node_start_lineno(node)
    sig_lines = source_lines[start - 1 : sig_end_excl]
    parts = [textwrap.dedent("\n".join(sig_lines))]

    for name in dep_members:
        for child in node.body:
            if (
                isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                and child.name == name
            ):
                full = _format_function(child, source_lines, "full")
                if full:
                    parts.append(full)
                break
    return "\n\n".join(parts)


def _format_class_with_redact(
    node: ast.ClassDef,
    source_lines: list[str],
    redact_member: Optional[str],
) -> str:
    """Return full class source. If ``redact_member`` matches a method name,
    the entire method (decorators + signature + body) is removed, leaving
    only a single comment placeholder so the target answer is fully hidden.
    """
    if not redact_member:
        return _node_source(node, source_lines)

    target_method: Optional[ast.AST] = None
    for child in node.body:
        if (
            isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            and child.name == redact_member
        ):
            target_method = child
            break
    if target_method is None:
        return _node_source(node, source_lines)

    # Class block as-is, then drop the lines belonging to the target method
    # (including any decorators that precede the def).
    class_lines = source_lines[node.lineno - 1 : node.end_lineno]
    method_start_lineno = _node_start_lineno(target_method)
    method_end_lineno = target_method.end_lineno

    start_idx = method_start_lineno - node.lineno  # 0-based within class_lines
    end_idx = method_end_lineno - node.lineno  # inclusive

    # Indent placeholder using the column of the method's def (or first deco).
    raw = source_lines[method_start_lineno - 1]
    indent_str = raw[: len(raw) - len(raw.lstrip())]

    new_lines = (
        class_lines[:start_idx]
        + [indent_str + f"# {redact_member} (target, hidden)"]
        + class_lines[end_idx + 1 :]
    )
    return textwrap.dedent("\n".join(new_lines))


def _find_instance_attr_setter(
    class_node: ast.ClassDef, attr_name: str,
) -> Optional[ast.AST]:
    """Return the class method that contains ``self.{attr_name} = ...``.

    This handles the common pattern where instance attributes are declared
    via assignment inside ``__init__`` (or another method), rather than as
    direct class members.
    """
    for child in class_node.body:
        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for stmt in ast.walk(child):
            if isinstance(stmt, ast.Assign):
                for t in stmt.targets:
                    if (
                        isinstance(t, ast.Attribute)
                        and isinstance(t.value, ast.Name)
                        and t.value.id == "self"
                        and t.attr == attr_name
                    ):
                        return child
            elif isinstance(stmt, ast.AnnAssign):
                tgt = stmt.target
                if (
                    isinstance(tgt, ast.Attribute)
                    and isinstance(tgt.value, ast.Name)
                    and tgt.value.id == "self"
                    and tgt.attr == attr_name
                ):
                    return child
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
