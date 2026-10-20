"""Choosing one candidate per line so that every rhyme pair holds.

A Problem has, for each line, the weights of its candidates (how well each
keeps the meaning) and, for some pairs of lines, the candidate pairs that are
allowed together (the ones that rhyme). The best choice maximizes the total
weight. solve_exact is a branch and bound over lines with the fewest
candidates first; solve_cpsat hands the same model to OR-Tools CP-SAT when it
is installed (the cpsat extra), which is what the auto method falls back
to on instances too big to enumerate. Without it, the fallback is the first
choice that keeps every pair, found the same way but without the bound.
"""

from __future__ import annotations

from dataclasses import dataclass, field

NODE_LIMIT = 200_000


@dataclass
class Problem:
    weights: list[list[float]]
    pairs: dict[tuple[int, int], set[tuple[int, int]]] = field(default_factory=dict)

    def allowed(self, a: int, i: int, b: int, j: int) -> bool:
        if a > b:
            a, i, b, j = b, j, a, i
        ok = self.pairs.get((a, b))
        return ok is None or (i, j) in ok


class TooBig(Exception):
    pass


def solve_exact(p: Problem, node_limit: int = NODE_LIMIT) -> list[int] | None:
    n = len(p.weights)
    if any(not ws for ws in p.weights):
        return None
    order = sorted(range(n), key=lambda k: len(p.weights[k]))
    best_rest = [0.0] * (n + 1)
    for depth in range(n - 1, -1, -1):
        best_rest[depth] = best_rest[depth + 1] + max(p.weights[order[depth]])
    ranked = {k: sorted(range(len(p.weights[k])), key=lambda c: -p.weights[k][c]) for k in order}
    choice: dict[int, int] = {}
    best: tuple[float, dict[int, int]] | None = None
    nodes = 0

    def walk(depth: int, total: float) -> None:
        nonlocal best, nodes
        nodes += 1
        if nodes > node_limit:
            raise TooBig
        if best is not None and total + best_rest[depth] <= best[0] + 1e-12:
            return
        if depth == n:
            best = (total, dict(choice))
            return
        line = order[depth]
        for c in ranked[line]:
            if all(p.allowed(line, c, other, oc) for other, oc in choice.items()):
                choice[line] = c
                walk(depth + 1, total + p.weights[line][c])
                del choice[line]

    walk(0, 0.0)
    if best is None:
        return None
    return [best[1][k] for k in range(n)]


def solve_cpsat(p: Problem, seconds: float = 10.0) -> list[int] | None:
    from ortools.sat.python import cp_model

    if any(not ws for ws in p.weights):
        return None
    model = cp_model.CpModel()
    x = [
        [model.new_bool_var(f"x{k}_{c}") for c in range(len(ws))] for k, ws in enumerate(p.weights)
    ]
    for row in x:
        model.add_exactly_one(row)
    for (a, b), ok in p.pairs.items():
        for i in range(len(x[a])):
            for j in range(len(x[b])):
                if (i, j) not in ok:
                    model.add_bool_or([x[a][i].Not(), x[b][j].Not()])
    model.maximize(
        sum(round(w * 1000) * x[k][c] for k, ws in enumerate(p.weights) for c, w in enumerate(ws))
    )
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    return [next(c for c, var in enumerate(row) if solver.value(var)) for row in x]


def cpsat_available() -> bool:
    try:
        import ortools.sat.python.cp_model  # noqa: F401
    except ImportError:
        return False
    return True


def solve(p: Problem, method: str = "auto") -> list[int] | None:
    if method == "exact":
        return solve_exact(p, node_limit=10**9)
    if method == "cpsat":
        return solve_cpsat(p)
    if method != "auto":
        raise ValueError(f"unknown solver {method!r}; use auto, exact or cpsat")
    try:
        return solve_exact(p)
    except TooBig:
        if cpsat_available():
            return solve_cpsat(p)
        return _first_fit(p)


def _first_fit(p: Problem, node_limit: int = NODE_LIMIT) -> list[int] | None:
    """The first choice that keeps every pair, trying each line's best
    candidates first: a backtracking search without the bound, for instances
    too big to optimize. None if there is none, or none within node_limit."""
    n = len(p.weights)
    if any(not ws for ws in p.weights):
        return None
    order = sorted(range(n), key=lambda k: len(p.weights[k]))
    ranked = {k: sorted(range(len(p.weights[k])), key=lambda c: -p.weights[k][c]) for k in order}
    choice: dict[int, int] = {}
    nodes = 0

    def walk(depth: int) -> bool:
        nonlocal nodes
        nodes += 1
        if nodes > node_limit:
            raise TooBig
        if depth == n:
            return True
        line = order[depth]
        for c in ranked[line]:
            if all(p.allowed(line, c, other, oc) for other, oc in choice.items()):
                choice[line] = c
                if walk(depth + 1):
                    return True
                del choice[line]
        return False

    try:
        found = walk(0)
    except TooBig:
        return None
    return [choice[k] for k in range(n)] if found else None
