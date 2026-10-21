import random

import pytest

from ashugh.solver import Problem, solve, solve_exact


def problem(n_lines, n_cands, seed, density=0.5):
    rng = random.Random(seed)
    weights = [[rng.random() for _ in range(n_cands)] for _ in range(n_lines)]
    pairs = {}
    for a in range(n_lines):
        for b in range(a + 1, n_lines):
            pairs[(a, b)] = {
                (i, j) for i in range(n_cands) for j in range(n_cands) if rng.random() < density
            }
    return Problem(weights, pairs)


def value(p, choice):
    return sum(p.weights[k][c] for k, c in enumerate(choice))


def test_exact_finds_the_best_compatible_choice():
    p = Problem([[1.0, 0.2], [0.9, 0.8]], {(0, 1): {(1, 0), (0, 1)}})
    assert solve_exact(p) == [0, 1]


def test_exact_reports_infeasible():
    p = Problem([[1.0], [1.0]], {(0, 1): set()})
    assert solve_exact(p) is None


def test_empty_line_is_infeasible():
    assert solve_exact(Problem([[1.0], []], {})) is None


def test_no_pairs_takes_each_best():
    assert solve_exact(Problem([[0.1, 0.9], [0.7, 0.3]], {})) == [1, 0]


@pytest.mark.parametrize("seed", range(20))
def test_exact_matches_brute_force(seed):
    from itertools import product

    p = problem(4, 4, seed)
    best = None
    for choice in product(range(4), repeat=4):
        if all((choice[a], choice[b]) in ok for (a, b), ok in p.pairs.items()):
            if best is None or value(p, choice) > value(p, best) + 1e-9:
                best = choice
    got = solve_exact(p)
    if best is None:
        assert got is None
    else:
        assert got is not None and abs(value(p, got) - value(p, best)) < 1e-9


@pytest.mark.parametrize("seed", range(10))
def test_cpsat_agrees_with_exact(seed):
    pytest.importorskip("ortools")
    p = problem(5, 5, seed, density=0.6)
    exact = solve_exact(p)
    sat = solve(p, method="cpsat")
    if exact is None:
        assert sat is None
    else:
        assert abs(value(p, sat) - value(p, exact)) < 1e-3


def test_unknown_method_is_refused():
    with pytest.raises(ValueError):
        solve(Problem([[1.0]], {}), method="magic")


TRAP = Problem(
    [[1.0, 0.1], [0.5, 0.5], [0.5, 0.5]],
    {(0, 1): {(0, 0), (1, 1)}, (1, 2): {(0, 1), (1, 0)}, (0, 2): {(1, 0)}},
)  # the best first candidate of line 0 leads nowhere; [1, 1, 0] works


@pytest.fixture
def too_big(monkeypatch):
    """Make the exact search give up, as on an instance too big to enumerate."""
    from ashugh import solver

    def give_up(p, node_limit=solver.NODE_LIMIT):
        raise solver.TooBig

    monkeypatch.setattr(solver, "solve_exact", give_up)
    return solver


def test_the_fallback_backtracks_to_a_choice_that_exists(too_big, monkeypatch):
    monkeypatch.setattr(too_big, "cpsat_available", lambda: False)
    assert solve(TRAP) == [1, 1, 0]


def test_the_fallback_reports_infeasible(too_big, monkeypatch):
    monkeypatch.setattr(too_big, "cpsat_available", lambda: False)
    assert solve(Problem([[1.0, 0.5], [1.0]], {(0, 1): set()})) is None
    assert solve(Problem([[1.0], []], {})) is None


@pytest.mark.parametrize("seed", range(20))
def test_the_fallback_keeps_every_pair_and_misses_no_solution(seed, too_big, monkeypatch):
    from itertools import product

    monkeypatch.setattr(too_big, "cpsat_available", lambda: False)
    p = problem(4, 4, seed, density=0.4)
    feasible = any(
        all((c[a], c[b]) in ok for (a, b), ok in p.pairs.items())
        for c in product(range(4), repeat=4)
    )
    got = solve(p)
    assert (got is not None) == feasible
    if got is not None:
        assert all((got[a], got[b]) in ok for (a, b), ok in p.pairs.items())


def test_auto_hands_big_instances_to_cpsat(too_big):
    pytest.importorskip("ortools")
    assert solve(TRAP) == [1, 1, 0]


def test_an_impossible_group_is_proved_so_without_walking_it():
    import time

    lines = 6
    weights = [[1.0 - c / 100 for c in range(25)] for _ in range(lines)]
    every = {(i, j) for i in range(25) for j in range(25)}
    pairs = {(a, b): set(every) for a in range(lines - 1) for b in range(a + 1, lines - 1)}
    pairs |= {(a, lines - 1): set() for a in range(lines - 1)}  # the last rhymes apart
    start = time.perf_counter()
    assert solve(Problem(weights, pairs), method="exact") is None
    assert solve(Problem(weights, pairs)) is None
    assert time.perf_counter() - start < 1  # the search walked 25^5 choices: 43 s
