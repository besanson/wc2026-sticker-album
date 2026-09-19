import ast
from pathlib import Path

import matchsim

# (relative path, function name) pairs allowed to reference these fields --
# strictly as a pass-through of user-typed scenario flags, never a
# derivation from data (CLAUDE.md section 1).
ALLOWED_DERIVATIONS = {("matchsim/models/lineup.py", "apply_scenario_flags")}
FORBIDDEN_TERMS = ("fitness_multiplier", "available", "minutes_cap")


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
            segment = ast.get_source_segment(source, node) or ""
            if any(term in segment for term in FORBIDDEN_TERMS):
                offenders.append(f"{rel}:{node.name}")

    assert not offenders, f"Functions referencing injury/fitness fields outside the allowed pass-through: {offenders}"
