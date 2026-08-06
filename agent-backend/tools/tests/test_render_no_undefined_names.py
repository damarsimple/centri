"""Every branch of the renderers must reference names that exist.

Renaming `rx, ry` -> `rpx, rpy` in `figures.fig_annotated_image` (2026-08-06) left two uses
behind in the omega-arc FALLBACK branch — the one taken only when the object sits near the
frame edge. `fan-4656` does not take that branch, so the render looked fine; `roundabout-4046`
and `turntable-1` both died with `NameError: name 'ry' is not defined`.

The unit tests at the time were static pattern checks and a full render of one clip, and
neither could see it. This walks the AST instead: for each function, every name that is LOADED
must be bound somewhere reachable — a parameter, an assignment, a comprehension target, an
import, a global, or a builtin. It costs milliseconds and covers every branch at once.
"""
import ast
import builtins
from pathlib import Path

import pytest

RENDER = Path(__file__).resolve().parents[2] / "workspace_lib" / "analysis" / "render"
TARGETS = sorted(p for p in RENDER.glob("*.py") if p.name != "__init__.py")
BUILTINS = set(dir(builtins))


def _module_level_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                names.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, ast.FunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.AsyncFunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                for n in ast.walk(t):
                    if isinstance(n, ast.Name):
                        names.add(n.id)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            for n in ast.walk(node.target):
                if isinstance(n, ast.Name):
                    names.add(n.id)
    return names


def _bound_in(fn):
    """Names bound anywhere inside `fn` (any branch — we only want 'exists at all')."""
    bound = set()
    for a in list(fn.args.args) + list(fn.args.kwonlyargs) + list(fn.args.posonlyargs):
        bound.add(a.arg)
    if fn.args.vararg:
        bound.add(fn.args.vararg.arg)
    if fn.args.kwarg:
        bound.add(fn.args.kwarg.arg)
    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bound.add(node.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                bound.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            bound.update(node.names)
        elif isinstance(node, (ast.comprehension,)):
            for n in ast.walk(node.target):
                if isinstance(n, ast.Name):
                    bound.add(n.id)
    return bound


@pytest.mark.parametrize("path", TARGETS, ids=lambda p: p.name)
def test_no_undefined_names_in_any_branch(path):
    tree = ast.parse(path.read_text(), filename=str(path))
    top = _module_level_names(tree) | BUILTINS
    problems = []
    for fn in [n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        bound = _bound_in(fn) | top
        for node in ast.walk(fn):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if node.id not in bound:
                    problems.append(f"{path.name}:{node.lineno} in {fn.name}(): "
                                    f"'{node.id}' is used but never bound")
    assert not problems, "\n".join(sorted(set(problems)))
