"""Dependency graph algorithms (Addendum 2 §B.4)."""

from __future__ import annotations

from km.infrastructure.config.models import DependencyError


def validate_dependency_graph(
    ontology_ids: set[str],
    dependencies: dict[str, list[str]],
) -> list[DependencyError]:
    """Validate self-reference, unknown targets, and cycles."""
    errors: list[DependencyError] = []

    for ontology_id, deps in dependencies.items():
        for dep in deps:
            if dep == ontology_id:
                errors.append(
                    DependencyError(
                        code="self_dependency",
                        severity="error",
                        message=(
                            f"Package '{ontology_id}' lists its own ontology_id "
                            "in dependencies"
                        ),
                        ontology_id=ontology_id,
                    )
                )
            elif dep not in ontology_ids:
                errors.append(
                    DependencyError(
                        code="unknown_dependency",
                        severity="error",
                        message=(
                            f"Package '{ontology_id}' depends on unknown "
                            f"ontology_id '{dep}'"
                        ),
                        ontology_id=ontology_id,
                    )
                )

    errors.extend(_detect_cycles(ontology_ids, dependencies))
    return errors


def _detect_cycles(
    ontology_ids: set[str],
    dependencies: dict[str, list[str]],
) -> list[DependencyError]:
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in ontology_ids}
    errors: list[DependencyError] = []

    def dfs(node: str, stack: list[str]) -> None:
        color[node] = GRAY
        stack.append(node)
        for dep in dependencies.get(node, []):
            if dep not in ontology_ids:
                continue
            if color[dep] == GRAY:
                cycle_start = stack.index(dep)
                cycle_path = stack[cycle_start:] + [dep]
                errors.append(
                    DependencyError(
                        code="dependency_cycle",
                        severity="error",
                        message="Dependency cycle detected: " + " → ".join(cycle_path),
                        ontology_id=node,
                        cycle_path=cycle_path,
                    )
                )
            elif color[dep] == WHITE:
                dfs(dep, stack)
        stack.pop()
        color[node] = BLACK

    for node in sorted(ontology_ids):
        if color[node] == WHITE:
            dfs(node, [])

    return errors


def transitive_closure(
    roots: set[str],
    dependencies: dict[str, list[str]],
) -> set[str]:
    """All dependency ontology_ids reachable from roots, excluding roots themselves."""
    closure: set[str] = set()
    stack = list(roots)
    visited: set[str] = set()

    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        for dep in dependencies.get(node, []):
            if dep not in roots:
                closure.add(dep)
            if dep not in visited:
                stack.append(dep)

    return closure


def effective_cache_set(
    explicit_ids: set[str],
    dependencies: dict[str, list[str]],
) -> set[str]:
    """B ∪ closure(B) per §B.4.4."""
    return explicit_ids | transitive_closure(explicit_ids, dependencies)
