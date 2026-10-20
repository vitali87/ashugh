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
