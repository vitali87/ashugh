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


def _consistent(p: Problem) -> list[list[int]] | None:
    """Each line's candidates, best first, that every paired line has a partner
    for (arc consistency): a candidate no partner allows is in no choice. None
    when a line is left with none, which proves at once that no choice keeps
    every pair (six lines that must share a rhyme, one that rhymes apart)."""
    domains = [set(range(len(ws))) for ws in p.weights]
    neighbors: dict[int, set[int]] = {}
    for a, b in p.pairs:
        neighbors.setdefault(a, set()).add(b)
        neighbors.setdefault(b, set()).add(a)
    queue = [arc for a, b in p.pairs for arc in ((a, b), (b, a))]
    while queue:
        a, b = queue.pop()
        lost = {i for i in domains[a] if not any(p.allowed(a, i, b, j) for j in domains[b])}
        if lost:
            domains[a] -= lost
            if not domains[a]:
                return None
            queue += [(c, a) for c in neighbors[a] if c != b]
    return [sorted(d, key=lambda c: -p.weights[k][c]) for k, d in enumerate(domains)]


def _search(p: Problem, node_limit: int, optimize: bool) -> list[int] | None:
    """Branch over lines, the fewest candidates first and each line's best first.
    Choosing a candidate strikes the ones its paired lines may no longer take
    (forward checking), so a dead end shows before it is walked into; with
    optimize, a branch whose remaining best cannot beat the best found stops."""
    n = len(p.weights)
    if any(not ws for ws in p.weights):
        return None
    domains = _consistent(p)
    if domains is None:
        return None
    order = sorted(range(n), key=lambda k: len(p.weights[k]))
    neighbors: dict[int, set[int]] = {k: set() for k in range(n)}
    for a, b in p.pairs:
        neighbors[a].add(b)
        neighbors[b].add(a)
    choice: dict[int, int] = {}
    best: tuple[float, dict[int, int]] | None = None
    nodes = 0

    def walk(depth: int, total: float, live: dict[int, list[int]]) -> bool:
        nonlocal best, nodes
        nodes += 1
        if nodes > node_limit:
            raise TooBig
        if optimize and best is not None:
            rest = sum(p.weights[k][cs[0]] for k, cs in live.items())
            if total + rest <= best[0] + 1e-12:
                return False
        if depth == n:
            best = (total, dict(choice))
            return not optimize
        line = order[depth]
        for c in live[line]:
            ahead: dict[int, list[int]] = {}
            for k, cs in live.items():
                if k == line:
                    continue
                if k in neighbors[line]:
                    cs = [x for x in cs if p.allowed(line, c, k, x)]
                    if not cs:
                        break
                ahead[k] = cs
            else:
                choice[line] = c
                if walk(depth + 1, total + p.weights[line][c], ahead):
                    return True
                del choice[line]
        return False

    walk(0, 0.0, {k: domains[k] for k in range(n)})
    if best is None:
        return None
    return [best[1][k] for k in range(n)]


def solve_exact(p: Problem, node_limit: int = NODE_LIMIT) -> list[int] | None:
    return _search(p, node_limit, optimize=True)


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
    candidates first: the same search without the bound, for instances too big
    to optimize. None if there is none, or none within node_limit."""
    try:
        return _search(p, node_limit, optimize=False)
    except TooBig:
        return None
