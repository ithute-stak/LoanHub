"""Read-only Alembic revision graph audit (standard library only).

Run from apps/backend: python3 -m scripts.audit_principal_x_alembic_graph
Never runs migrations or connects to a database.
"""
from __future__ import annotations

import ast
from pathlib import Path


def _literal_assignment(tree, name):
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            if isinstance(node, ast.Assign):
                targets = node.targets
            else:
                targets = [node.target]
            if any(isinstance(t, ast.Name) and t.id == name for t in targets):
                try:
                    return ast.literal_eval(node.value)
                except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
                    raise ValueError(f"{name} is not a literal")
    raise ValueError(f"Missing {name}")


def audit_graph(folder: Path):
    revisions = {}
    errors = []
    for path in sorted(folder.glob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            revision = _literal_assignment(tree, "revision")
            parent = _literal_assignment(tree, "down_revision")
            if not isinstance(revision, str) or not revision:
                raise ValueError("Invalid revision")
            if parent is None:
                parents = ()
            elif isinstance(parent, str):
                parents = (parent,)
            elif isinstance(parent, tuple) and all(isinstance(x, str) for x in parent):
                parents = parent
            else:
                raise ValueError("Invalid down_revision")
            if revision in revisions:
                errors.append(f"Duplicate revision {revision}: {path.name}")
            revisions[revision] = (path.name, parents)
        except (SyntaxError, UnicodeError, OSError, ValueError) as exc:
            errors.append(f"{path.name}: {exc}")
    referenced = {parent for _, parents in revisions.values() for parent in parents}
    for parent in sorted(referenced - revisions.keys()):
        errors.append(f"Missing parent revision: {parent}")
    heads = sorted(set(revisions) - referenced)
    if len(heads) != 1:
        errors.append(f"Expected one migration head, found {len(heads)}: {heads}")
    return heads, errors, len(revisions)


def main():
    folder = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    heads, errors, count = audit_graph(folder)
    print(f"Parsed {count} Alembic revisions; heads: {heads}")
    for error in errors:
        print("BLOCKED:", error)
    if errors:
        return 1
    print("Graph audit passed. Migration creation still requires review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
