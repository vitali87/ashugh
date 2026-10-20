"""fit: repair the lines of a song that break its spec.

1. Scan the song. Every line with a line-level error, and every line of a
   broken rhyme group, becomes a variable; its own text stays a candidate when
   it passes on its own.
2. A proposer writes candidates. Each one is analyzed and checked in its slot;
   the ones that fail are remembered with the reason.
3. Per rhyme group, the solver picks one candidate per line so that every
   member rhymes with the group's first line and the least meaning is lost.
4. Where nothing fits, the next round asks again, aimed at what blocked it:
   the near misses and why they failed, or the words the line must rhyme with.
   This is column generation with the proposer as the pricing oracle.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from . import lyrics, meter, rhyme
from .proposers import Proposer, Request
from .scan import ENDING_NAMES, LineReport, Report, UnitReport, check_line, reanalyze, scan
from .solver import Problem, solve
from .spec import Spec

MAX_LINE = 300
PUNCT_RE = re.compile(r"[,.;:!?…։՝—-]+\s*$")  # not ՛ ՜ ՞: they mark a stressed vowel
TO_ARMENIAN = str.maketrans({".": "։"})
FROM_ARMENIAN = str.maketrans({"։": ".", "՝": ","})
LINE_LEVEL = {"rhyme", "scheme"}


@dataclass
class Candidate:
    text: str
    report: LineReport
    weight: float
    original: bool = False


@dataclass
class Change:
    line: int
    old: str
    new: str
    weight: float


@dataclass
class Unresolved:
    line: int
    reasons: list[str]


@dataclass
class FitResult:
    text: str
    report: Report
    changes: list[Change]
    unresolved: list[Unresolved]
    rounds: int
    requests: int

    @property
    def ok(self) -> bool:
        return self.report.ok and not self.unresolved

    def as_dict(self) -> dict:
        from .report import as_dict

        return {
            "ok": self.ok,
            "rounds": self.rounds,
            "requests": self.requests,
            "changes": [vars(c) for c in self.changes],
            "unresolved": [vars(u) for u in self.unresolved],
            "text": self.text,
            "report": as_dict(self.report),
        }


Weigh = Callable[[str, str, "float | None"], float]


def similarity(a: str, b: str) -> float:
    """Share of word stems two lines have in common (Jaccard)."""

    def stems(s: str) -> set[str]:
        return {w[:4] for w in re.findall(r"[^\W\d_]+", s.lower())}

    x, y = stems(a), stems(b)
    return len(x & y) / len(x | y) if x | y else 0.0


def default_weight(original: str, text: str, faithfulness: float | None) -> float:
    """Keeping the line is worth 1; a rewrite 0.3 to 0.9 by how much it keeps."""
    if faithfulness is not None:
        return 0.3 + 0.6 * max(0.0, min(1.0, faithfulness))
    return 0.3 + 0.6 * similarity(original, text)


@dataclass
class _Var:
    lr: LineReport
    unit: UnitReport
    pool: list[Candidate] = field(default_factory=list)
    rejected: list[tuple[str, str]] = field(default_factory=list)  # (candidate, why it failed)
    seen: set[str] = field(default_factory=set)
    group: str | None = None
    chosen: Candidate | None = None
    blocked: list[str] = field(default_factory=list)  # why the last round did not settle it

    @property
    def number(self) -> int:
        return self.lr.line.number


def line_errors(lr: LineReport) -> list:
    return [i for i in lr.issues if i.severity == "error" and i.code not in LINE_LEVEL]


def fit_song(
    text: str,
    spec: Spec | None = None,
    proposer: Proposer | None = None,
    rounds: int = 3,
    n: int = 6,
    solver: str = "auto",
    lang: str | None = None,
    weigh: Weigh = default_weight,
    keep_original: bool = True,
    extra: Callable[[_Var, Request], None] | None = None,
) -> FitResult:
    spec = spec or Spec()
    report = scan(text, spec, lang=lang)
    variables, groups = _variables(report, keep_original)
    if not variables:
        return FitResult(text, report, [], [], 0, 0)
    if proposer is None:
        raise ValueError("fit needs a proposer for the lines that fail")

    lines_by_number = {lr.line.number: lr for lr in report.lines}
    used, asked = run(
        variables, groups, lines_by_number, spec, proposer, rounds, n, solver, lang, weigh, extra
    )
    changes, unresolved = [], []
    for k in sorted(variables):
        var = variables[k]
        if var.chosen is None:
            reasons = (
                var.blocked or [e.message for e in line_errors(var.lr)] or ["no candidate fit"]
            )
            unresolved.append(Unresolved(k, reasons))
        elif not var.chosen.original:
            changes.append(
                Change(k, var.lr.line.text, var.chosen.text, round(var.chosen.weight, 3))
            )
    new_text = replace_lines(text, {c.line: c.new for c in changes})
    final = scan(new_text, spec, lang=lang) if changes else report
    return FitResult(new_text, final, changes, unresolved, used, asked)


def requests_for(
    text: str, spec: Spec | None = None, n: int = 6, lang: str | None = None
) -> list[Request]:
    """The first round of requests fit would send, for a proposer outside ashugh."""
    spec = spec or Spec()
    report = scan(text, spec, lang=lang)
    variables, groups = _variables(report, keep_original=True)
    lines = {lr.line.number: lr for lr in report.lines}
    return [_request(variables[k], variables, groups, lines, n, None) for k in sorted(variables)]


def run(
    variables: dict[int, _Var],
    groups: dict[str, list[int]],
    lines: dict[int, LineReport],
    spec: Spec,
    proposer: Proposer,
    rounds: int,
    n: int,
    solver: str,
    lang: str | None,
    weigh: Weigh,
    extra=None,
    partners_from_lines: bool = True,
) -> tuple[int, int]:
    """The propose, check and solve loop; returns (rounds used, requests sent)."""
    pending = set(variables)
    used = asked = 0
    for _ in range(rounds):
        if not pending:
            break
        requests = [
            _request(variables[k], variables, groups, lines, n, extra, partners_from_lines)
            for k in sorted(pending)
        ]
        answers = proposer.propose(requests)
        used += 1
        asked += len(requests)
        for req in requests:
            var = variables[req.line]
            for raw in answers.get(req.id, []) or []:
                _consider(var, raw, spec, lang, weigh)
        pending = _settle(variables, groups, lines, solver)
    return used, asked


def _variables(report: Report, keep_original: bool, everything: bool = False):
    variables: dict[int, _Var] = {}
    groups: dict[str, list[int]] = {}
    members: dict[str, list[LineReport]] = {}
    for u_id, unit in enumerate(report.units):
        scope = unit.scope or str(u_id)  # stanzas of one spaced scheme share their letters
        for lr in unit.lines:
            g = unit.rule.rhyme_at(lr.line.index)
            if g is not None:
                members.setdefault(f"{scope}:{g}", []).append(lr)
    broken = {
        g for g, lrs in members.items() if any(i.code == "rhyme" for lr in lrs for i in lr.issues)
    }
    group_of = {lr.line.number: g for g, lrs in members.items() for lr in lrs}
    for unit in report.units:
        for lr in unit.lines:
            g = group_of.get(lr.line.number)
            if everything or line_errors(lr) or g in broken:
                variables[lr.line.number] = _Var(lr, unit, group=g)
    for g, lrs in members.items():
        if any(lr.line.number in variables for lr in lrs) and len(lrs) > 1:
            groups[g] = [lr.line.number for lr in lrs]
    for var in variables.values():
        var.seen.add(_norm(var.lr.line.text))
        if keep_original and not line_errors(var.lr):
            var.pool.append(Candidate(var.lr.line.text, var.lr, 1.0, original=True))
        if var.group not in groups:
            var.group = None
    return variables, groups


def _norm(text: str) -> str:
    return " ".join(text.split()).lower()


def _clean(raw) -> tuple[str, float | None] | None:
    faith = None
    if isinstance(raw, dict):
        faith = raw.get("faithfulness")
        faith = (
            float(faith)
            if isinstance(faith, (int, float)) and not isinstance(faith, bool)
            else None
        )
        raw = raw.get("text")
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text or "\n" in text or "\r" in text or len(text) > MAX_LINE:
        return None
    if "[" in text or "]" in text or not lyrics.tokenize(text):
        return None  # a section tag, a backing vocal or punctuation: nothing to sing
    return text, faith


def _consider(var: _Var, raw, spec: Spec, lang: str | None, weigh: Weigh) -> None:
    cleaned = _clean(raw)
    if cleaned is None:
        return
    text, faith = cleaned
    key = _norm(text)
    if key in var.seen:
        return
    var.seen.add(key)
    line = reanalyze(var.lr.line, text, spec, lang)
    lr = check_line(line, var.unit.rule, var.unit.meter, var.unit.meter_source)
    errors = line_errors(lr)
    if errors:
        var.rejected.append((text, errors[0].message))
        return
    var.pool.append(Candidate(text, lr, weigh(var.lr.line.text, text, faith)))


def _fixed(lr: LineReport) -> Candidate:
    return Candidate(lr.line.text, lr, 1.0, original=True)


def _settle(
    variables: dict[int, _Var],
    groups: dict[str, list[int]],
    lines: dict[int, LineReport],
    method: str,
) -> set[int]:
    """Choose candidates where possible; return the lines that need another round."""
    pending: set[int] = set()
    for var in variables.values():
        if var.group is None:
            var.chosen = max(var.pool, key=lambda c: c.weight) if var.pool else None
            if var.chosen is None:
                pending.add(var.number)
                var.blocked = ["no candidate passed the line's own checks"]
    for numbers in groups.values():
        pools = [variables[k].pool if k in variables else [_fixed(lines[k])] for k in numbers]
        var_numbers = [k for k in numbers if k in variables]
        problem = _problem(pools, variables[var_numbers[0]].unit.rule.min_rhyme)
        choice = solve(problem, method) if all(pools) else None
        if choice is None:
            for k in var_numbers:
                variables[k].chosen = None
                pending.add(k)
                variables[k].blocked = (
                    ["no candidate passed the line's own checks"]
                    if not variables[k].pool
                    else ["no combination of candidates kept the rhyme"]
                )
            continue
        for k, c in zip(numbers, choice):
            if k in variables:
                variables[k].chosen = variables[k].pool[c]
                variables[k].blocked = []
    return pending


def _problem(pools: list[list[Candidate]], min_rhyme: str) -> Problem:
    floor = rhyme.THRESHOLD[min_rhyme]
    weights = [[c.weight for c in pool] for pool in pools]
    pairs: dict[tuple[int, int], set[tuple[int, int]]] = {}
    head = pools[0]
    for b in range(1, len(pools)):
        ok = set()
        for i, x in enumerate(head):
            for j, y in enumerate(pools[b]):
                s, tx, ty = rhyme.match(x.report.tails, y.report.tails)
                same_word = tx is not None and ty is not None and tx.spelling == ty.spelling
                if s >= floor and not (same_word and not (x.original and y.original)):
                    ok.add((i, j))
        pairs[(0, b)] = ok
    return Problem(weights, pairs)


def _request(
    var: _Var,
    variables: dict[int, _Var],
    groups: dict[str, list[int]],
    lines: dict[int, LineReport],
    n: int,
    extra,
    partners_from_lines: bool = True,
) -> Request:
    lr, rule = var.lr, var.unit.rule
    ln = lr.line
    idx = ln.index
    syllables = rule.syllables_at(idx)
    want_ending = rule.ending_at(idx)
    meter_name = var.unit.meter if var.unit.meter_source == "spec" else None
    feet = rule.feet_at(idx) if meter_name else None
    template = None
    if meter_name in meter.CLASSICAL:
        length = syllables
        if length is None and feet is not None:
            length = meter.length(meter_name, feet, want_ending if want_ending is not None else 0)
        if length:
            period, phase = meter.CLASSICAL[meter_name]
            last = length - 1  # the last beat: nothing after it is stressed
            if want_ending is not None:
                last = length - 1 - want_ending
            elif feet is not None:
                last = phase + period * (feet - 1)
            template = "".join(
                "/" if p % period == phase and p <= last else "x" for p in range(length)
            )
    rhyme_with, sound = [], None
    if var.group is not None:
        for k in groups[var.group]:
            if k == ln.number:
                continue
            current = _current(variables.get(k), lines[k] if partners_from_lines else None)
            t = current.tail if current else None
            if t is not None:
                rhyme_with.append(t.word)
                sound = sound or t.sound
    problems = [
        f"{i.message}" + (f" ({i.detail})" if i.detail else "")
        for i in lr.issues
        if i.severity == "error"
    ]
    problems.extend(b for b in var.blocked if b not in problems)
    numbers = sorted(lines)
    at = numbers.index(ln.number)
    before = [lines[k].line.text for k in numbers[max(0, at - 2) : at]]
    after = [lines[k].line.text for k in numbers[at + 1 : at + 3]]
    req = Request(
        id=f"L{ln.number}",
        line=ln.number,
        lang=ln.lang,
        original=ln.text,
        section=ln.section,
        before=before,
        after=after,
        syllables=syllables,
        tolerance=rule.tolerance,
        meter=meter_name,
        feet=feet,
        template=template,
        ending=ENDING_NAMES.get(want_ending) if want_ending is not None else None,
        rhyme_with=rhyme_with,
        rhyme_sound=sound,
        avoid_final=list(rule.forbid_final),
        problems=problems,
        rejected=[f"{text} — {why}" for text, why in var.rejected[-8:]],
        n=n,
    )
    if extra is not None:
        extra(var, req)
    return req


def _current(var: _Var | None, original: LineReport | None) -> LineReport | None:
    """The partner line as it stands: its chosen or best candidate, else its text."""
    if var is None:
        return original
    best = var.chosen or max(var.pool, key=lambda c: c.weight, default=None)
    return best.report if best else original


def replace_lines(text: str, new: dict[int, str], lang: str | None = None) -> str:
    """text with the given 1-based lines replaced, indentation and line endings kept.

    A line's closing punctuation stays when the new text has none, written the
    way lang writes it (the Armenian full stop is ։) when lang is given.
    """
    if not new:
        return text
    lines = lyrics.split_lines(text, keepends=True)
    for number, content in new.items():
        if 1 <= number <= len(lines):
            line = lines[number - 1]
            body = line.rstrip("\r\n")
            ending = line[len(body) :]
            lead = body[: len(body) - len(body.lstrip())]
            body = body[len(lead) :]
            mark = PUNCT_RE.search(body)
            if mark and not PUNCT_RE.search(content):
                tail = mark.group(0)
                if lang is not None and tail.strip() in (".", "։", "՝"):  # not an ellipsis
                    tail = tail.translate(TO_ARMENIAN if lang == "hy" else FROM_ARMENIAN)
                content += tail  # keep the line's closing comma or full stop
            lines[number - 1] = lead + content + ending
    return "".join(lines)
