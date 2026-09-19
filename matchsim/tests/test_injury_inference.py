import ast
from pathlib import Path

import matchsim

# (relative path, function name) pairs allowed to derive (assign a bare-name
# value to) these fields -- strictly as a pass-through of user-typed scenario
# flags, never a derivation from data (CLAUDE.md section 1). Reading an
# already-derived value back out (flags.available, flags.fitness_multiplier)
# is not a derivation and is fine anywhere -- e.g. build_lineup_strength
# applies a scenario's fitness_multiplier as a weight, it doesn't compute one.
ALLOWED_DERIVATIONS = {("matchsim/models/lineup.py", "apply_scenario_flags")}
FORBIDDEN_NAMES = {"fitness_multiplier", "available", "minutes_cap"}


def _assigned_names(node: ast.AST):
    """Bare-name assignment targets anywhere under `node`. An attribute read
    (obj.available) or a passed-through keyword argument isn't an assignment
    target, so it's excluded by construction -- only naming a new local or
    return value after one of these fields counts as deriving it."""
    for child in ast.walk(node):
        if isinstance(child, ast.Assign):
            targets = child.targets
        elif isinstance(child, (ast.AnnAssign, ast.AugAssign)):
            targets = [child.target]
        else:
            continue
        for t in targets:
            if isinstance(t, ast.Name):
                yield t.id


def test_no_injury_inference():
    pkg_root = Path(matchsim.__file__).resolve().parent
    offenders = []

    for path in sorted(pkg_root.rglob("*.py")):
        rel = path.relative_to(pkg_root.parent).as_posix()
        source = path.read_text()
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if (rel, node.name) in ALLOWED_DERIVATIONS:
                continue
            if set(_assigned_names(node)) & FORBIDDEN_NAMES:
                offenders.append(f"{rel}:{node.name}")

    assert not offenders, f"Functions that compute/assign injury-fitness fields outside the allowed pass-through: {offenders}"
