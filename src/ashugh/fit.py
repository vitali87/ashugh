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
from functools import cached_property

from . import lang as languages
from . import lyrics, meter, rhyme
from .proposers import Proposer, ProposerError, Request
from .scan import (
    ENDING_NAMES,
    REFRAIN,
    LineReport,
    Report,
    UnitReport,
    check_line,
    forms_of_one_word,
    reanalyze,
    rhyme_alternatives,
    rhyme_head,
    scan,
)
from .solver import Problem, solve
from .spec import Spec

MAX_LINE = 300
PUNCT_RE = re.compile(r"[,.;:!?…։՝—-]+\s*$")  # not ՛ ՜ ՞: they mark a stressed vowel
ASIDE_PUNCT = ",.;:!?…։՝"
TO_ARMENIAN = str.maketrans({".": "։"})
FROM_ARMENIAN = str.maketrans({"։": ".", "՝": ","})
LINE_LEVEL = {"rhyme", "scheme"}
REFRAIN_WEIGHT = 0.25  # under any rewrite (0.3 at least): a candidate that ends a refrain wins


@dataclass
class Candidate:
    text: str
    report: LineReport
    weight: float
    original: bool = False

    @cached_property
    def head(self) -> tuple | None:
        """Its rhyme word as forms_of_one_word compares it, found once for all pairs."""
        return rhyme_head(self.report)

    @cached_property
    def rhyme_key(self) -> tuple:
        """All that its rhyme with another candidate depends on: candidates that
        end alike (a thousand lines on cry, shy, pie) are judged once a pair."""
        tail = self.report.tail
        return (tuple(_rhymes(self)), tail and tail.spelling, self.original, self.head)


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
    rejected: list[dict] = field(default_factory=list)  # {"text", "why"} per candidate


@dataclass
class FitResult:
    text: str
    report: Report
    changes: list[Change]
    unresolved: list[Unresolved]
    rounds: int
    requests: int
    warnings: list[str] = field(default_factory=list)  # not failures: asides left out

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
            "warnings": self.warnings,
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
    offered: int = 0  # candidates the proposer gave
    malformed: list[str] = field(default_factory=list)  # why unusable ones were dropped
    written: bool = True  # the line as written may stand (not in a translation)

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
    text = lyrics.clean(text)
    report = scan(text, spec, lang=lang)
    variables, groups = _variables(report, keep_original)
    if not variables:
        return FitResult(text, report, [], [], 0, 0)
    if proposer is None:
        raise ValueError("fit needs a proposer for the lines that fail")

    lines_by_number = {lr.line.number: lr for lr in report.lines}
    warnings: list[str] = []
    used, asked = run(
        variables,
        groups,
        lines_by_number,
        spec,
        proposer,
        rounds,
        n,
        solver,
        lang,
        weigh,
        extra,
        warnings=warnings,
    )
    changes, unresolved = [], []
    for k in sorted(variables):
        var = variables[k]
        if var.chosen is None:
            reasons = (
                var.blocked or [e.message for e in line_errors(var.lr)] or ["no candidate fit"]
            )
            rejected = [{"text": t, "why": why} for t, why in var.rejected]
            unresolved.append(Unresolved(k, reasons, rejected))
        elif not var.chosen.original:
            changes.append(
                Change(k, var.lr.line.text, var.chosen.text, round(var.chosen.weight, 3))
            )
    new_text = replace_lines(text, {c.line: c.new for c in changes})
    warnings += _asides_left_out(text, changes)
    final = scan(new_text, spec, lang=lang) if changes else report
    return FitResult(new_text, final, changes, unresolved, used, asked, warnings)


def _asides_left_out(text: str, changes: list[Change]) -> list[str]:
    """The backing vocals inside a replaced line, which the new line has no place
    for: those that end it are carried, these are named to put back by hand."""
    raw = lyrics.split_lines(text)
    out = []
    for c in changes:
        body = raw[c.line - 1] if c.line <= len(raw) else ""
        tail = _trailing_asides(body)
        end = tail[0] if tail else len(body)
        inner = [body[a:b] for a, b in lyrics.aside_spans(body) if b <= end]
        if inner and "(" not in c.new:
            out.append(f"L{c.line}: {' '.join(inner)} inside the line is left out of the new one")
    return out


def requests_for(
    text: str,
    spec: Spec | None = None,
    n: int = 6,
    lang: str | None = None,
    warnings: list[str] | None = None,
) -> list[Request]:
    """The first round of requests fit would send, for a proposer outside ashugh;
    warnings, when given, gets what the spec itself gets wrong (a slot no line
    can fill, a table that matches no section)."""
    spec = spec or Spec()
    report = scan(text, spec, lang=lang)
    if warnings is not None:
        warnings += [
            f"{i.message}: {i.detail}" if i.detail else i.message
            for i in report.issues
            if i.code == "spec"
        ]
    variables, groups = _variables(report, keep_original=True)
    lines = {lr.line.number: lr for lr in report.lines}
    later = _later_copies(variables)
    return [
        _request(variables[k], variables, groups, lines, n, None)
        for k in sorted(variables)
        if k not in later
    ]


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
    warnings: list[str] | None = None,
) -> tuple[int, int]:
    """The propose, check and solve loop; returns (rounds used, requests sent). A
    proposer failing after the first round ends the loop with what it has, and
    says so in warnings; failing in the first, it raises."""
    pending = set(variables)
    later = _later_copies(variables)
    used = asked = 0
    for _ in range(rounds):
        if not pending - set(later):
            break
        requests = [
            _request(variables[k], variables, groups, lines, n, extra, partners_from_lines)
            for k in sorted(pending - set(later))
        ]
        try:
            answers = proposer.propose(requests)
        except ProposerError as e:
            if not used:
                raise
            if warnings is not None:
                warnings.append(f"round {used + 1} failed ({e}); kept the earlier rounds' results")
            break
        used += 1
        asked += len(requests)
        for req in requests:
            var = variables[req.line]
            for raw in answers.get(req.id, []) or []:
                var.offered += 1
                _consider(var, raw, spec, lang, weigh)
        pending = _settle(variables, groups, lines, solver)
        pending -= _same_repair_for_copies(variables, later, spec, lang, weigh)
    return used, asked


def _later_copies(variables: dict[int, _Var]) -> dict[int, int]:
    """Lines written again (a chorus's second time), each to its first copy's number."""
    first: dict[str, int] = {}
    later: dict[int, int] = {}
    for k in sorted(variables):
        text = _norm(variables[k].lr.line.text)
        if text in first:
            later[k] = first[text]
        else:
            first[text] = k
    return later


def _same_repair_for_copies(
    variables: dict[int, _Var], later: dict[int, int], spec: Spec, lang, weigh: Weigh
) -> set[int]:
    """A line written twice (a chorus) gets its first copy's repair wherever that
    repair passes the copy's own checks, so a song never sings two versions;
    returns the copies so settled."""
    settled = set()
    for k, src in later.items():
        var, source = variables[k], variables[src]
        if source.chosen is None:
            continue
        if var.chosen is None or _norm(var.chosen.text) != _norm(source.chosen.text):
            var.seen.discard(_norm(source.chosen.text))
            _consider(var, source.chosen.text, spec, lang, weigh)
            same = [c for c in var.pool if _norm(c.text) == _norm(source.chosen.text)]
            if same:
                var.chosen, var.blocked = same[0], []
        if var.chosen is not None:
            settled.add(k)
    return settled


def _variables(report: Report, keep_original: bool, everything: bool = False):
    variables: dict[int, _Var] = {}
    groups: dict[str, list[int]] = {}
    members: dict[str, list[LineReport]] = {}
    unit_of = {lr.line.number: unit for unit in report.units for lr in unit.lines}
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
            for lr in lrs:  # the readings a new partner may choose for a line kept as is
                unit = unit_of[lr.line.number]
                lr.alt_tails = rhyme_alternatives(lr, unit.rule, unit.meter, unit.meter_source)
    for var in variables.values():
        var.seen.add(_norm(var.lr.line.text))
        var.written = keep_original
        if keep_original and not line_errors(var.lr):
            # a refrain is fine if meant, but a candidate offered for it is meant to
            # end it: the line as written then weighs less than any rewrite
            refrain = any(i.detail == REFRAIN for i in var.lr.issues)
            weight = REFRAIN_WEIGHT if refrain else 1.0
            var.pool.append(Candidate(var.lr.line.text, var.lr, weight, original=True))
        if var.group not in groups:
            var.group = None
    return variables, groups


def _norm(text: str) -> str:
    return " ".join(text.split()).lower()


def _clean(raw) -> tuple[str, float | None] | str:
    """The candidate's line and faithfulness, or why it is no line to check."""
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
        return "not text"
    text = raw.strip()
    if "\n" in text or "\r" in text:
        return "more than one line"
    if len(text) > MAX_LINE:
        return f"longer than {MAX_LINE} characters"
    if "[" in text or "]" in text:
        return "a section tag or bracket, not a line"
    if not lyrics.tokenize(text):
        return "nothing to sing"
    return text, faith


def _consider(var: _Var, raw, spec: Spec, lang: str | None, weigh: Weigh) -> None:
    cleaned = _clean(raw)
    if isinstance(cleaned, str):  # never a line to write into the song, so not rejected
        var.malformed.append(cleaned)
        return
    text, faith = cleaned
    key = _norm(text)
    if key in var.seen:
        return
    var.seen.add(key)
    want = lang or var.lr.line.lang
    tokens = lyrics.tokenize(text)
    written = languages.detect(tokens)
    if want == "hy" and written == "en" and languages.latin_armenian(tokens):
        written = "hy"  # Ari u el mi gna: Armenian typed in Latin letters
    if want in languages.ANALYZERS and written and written != want:
        name = languages.NAMES.get(want, want)
        var.rejected.append((text, f"not in {name}"))  # a translation left in its source
        return
    line = reanalyze(var.lr.line, text, spec, lang)
    lr = check_line(line, var.unit.rule, var.unit.meter, var.unit.meter_source)
    errors = line_errors(lr)
    if errors:
        var.rejected.append((text, errors[0].message))
        return
    if var.group is not None:
        lr.alt_tails = rhyme_alternatives(lr, var.unit.rule, var.unit.meter, var.unit.meter_source)
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
                var.blocked = [_why_empty(var)]
    for numbers in groups.values():
        pools = [variables[k].pool if k in variables else [_fixed(lines[k])] for k in numbers]
        var_numbers = [k for k in numbers if k in variables]
        problem = _problem(pools)
        choice = solve(problem, method) if all(pools) else None
        empty = [k for k in var_numbers if not variables[k].pool]
        if choice is None and empty and all(variables[k].written for k in empty):
            # A line with no usable candidate stays as written, unresolved, and its
            # partners may still be fixed to rhyme with it as it stands: line / nine.
            pools = [p or [_fixed(lines[k])] for k, p in zip(numbers, pools)]
            choice = solve(_problem(pools), method)
            if choice is not None and any(
                not pools[j][c].original for j, c in enumerate(choice) if numbers[j] not in empty
            ):
                for k, c in zip(numbers, choice):
                    if k in empty:
                        var = variables[k]
                        var.chosen, var.blocked = None, [_why_empty(var)]
                        pending.add(k)
                    elif k in variables:
                        variables[k].chosen = pools[numbers.index(k)][c]
                        variables[k].blocked = []
                continue
            choice = None
        if choice is None:
            for k in var_numbers:
                var = variables[k]
                passing = [c for c in var.pool if c.original and not line_errors(c.report)]
                if passing and empty:
                    var.chosen, var.blocked = passing[0], []  # it fits; its partner does not
                    continue
                var.chosen = None
                pending.add(k)
                if not var.pool:
                    var.blocked = [_why_empty(var)]
                elif empty:
                    partners = ", ".join(f"L{j}" for j in empty)
                    var.blocked = [f"its rhyme partner {partners} has no usable candidate"]
                elif not var.offered:
                    var.blocked = ["no candidates given, and the line as written breaks the rhyme"]
                else:
                    var.blocked = ["no combination of candidates kept the rhyme"]
                    _same_word_rejections(var, [lines[j] for j in numbers if j != k])
            continue
        for k, c in zip(numbers, choice):
            if k in variables:
                variables[k].chosen = variables[k].pool[c]
                variables[k].blocked = []
    return pending


def _same_word_rejections(var: _Var, partners: list[LineReport]) -> None:
    """Name the candidates the solver could not take for ending on a partner's
    own rhyme word, which no per-line check rejects."""
    words = {p.tail.spelling: p.line.number for p in partners if p.tail is not None}
    for c in var.pool:
        tail = c.report.tail
        if c.original or tail is None or tail.spelling not in words:
            continue
        why = f"ends on «{tail.word}», the word L{words[tail.spelling]} rhymes on"
        if (c.text, why) not in var.rejected:
            var.rejected.append((c.text, why))


def _why_empty(var: _Var) -> str:
    if not var.offered:
        return "no candidates given"
    if len(var.malformed) == var.offered:
        return f"no usable candidate: {var.malformed[0]}"
    return "no candidate passed the line's own checks"


def _problem(pools: list[list[Candidate]]) -> Problem:
    """Each line against one earlier member of its group, judged by its own
    stanza's min_rhyme, with the readings a partner may choose (облака́ beside
    свысока́); and no two lines on the same rhyme word unless both were written
    that way. A line's anchor is the earlier member its candidates rhyme with
    most, so the chosen lines hold together as scan asks (friends with end where
    pen would not do), and the first line only where nothing else fits better."""
    weights = [[c.weight for c in pool] for pool in pools]
    pairs: dict[tuple[int, int], set[tuple[int, int]]] = {}
    alike = [_alike(pool) for pool in pools]

    def allowed(a: int, b: int, test: Callable[[Candidate, Candidate], bool]):
        return {
            (i, j)
            for xs in alike[a].values()
            for ys in alike[b].values()
            if test(pools[a][xs[0]], pools[b][ys[0]])
            for i in xs
            for j in ys
        }

    for b in range(1, len(pools)):
        rhymed = {a: allowed(a, b, _rhyme_ok) for a in range(b)}
        anchor = max(range(b), key=lambda a: (len(rhymed[a]), -a))
        pairs[(anchor, b)] = rhymed[anchor]
        for a in range(b):
            if a == anchor:
                continue
            ok = allowed(
                a, b, lambda x, y: (x.original and y.original) or not _same_rhyme_word(x, y)
            )
            if len(ok) < len(pools[a]) * len(pools[b]):
                pairs[(a, b)] = ok
    return Problem(weights, pairs)


def _alike(pool: list[Candidate]) -> dict[tuple, list[int]]:
    """A pool's candidates grouped by rhyme_key, in order."""
    out: dict[tuple, list[int]] = {}
    for i, c in enumerate(pool):
        out.setdefault(c.rhyme_key, []).append(i)
    return out


def _rhyme_ok(x: Candidate, y: Candidate) -> bool:
    """y rhymes with x at y's min_rhyme, and not on the same word or another form
    of it (сердца / сердце) unless both lines were written that way."""
    s, tx, ty = rhyme.match(_rhymes(x), _rhymes(y))
    if s < rhyme.THRESHOLD[y.report.min_rhyme]:
        return False
    if x.original and y.original:
        return True
    same_word = tx is not None and ty is not None and tx.spelling == ty.spelling
    return not (same_word or forms_of_one_word(x.head, y.head))


def _rhymes(c: Candidate) -> list:
    return c.report.tails + c.report.alt_tails


def _same_rhyme_word(x: Candidate, y: Candidate) -> bool:
    a, b = x.report.tail, y.report.tail
    return a is not None and b is not None and a.spelling == b.spelling


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
    rhyme_with, sound, partner_ending = [], None, None
    moving: list[int] = []  # partners whose rhyme word must change too
    if var.group is not None:
        members = groups[var.group]
        settled = [  # partners that may stay: kept, chosen, or passing every check
            k
            for k in members
            if k != ln.number
            and (
                k not in variables
                or variables[k].chosen is not None
                or not (line_errors(variables[k].lr) or _breaks_rhyme(variables[k].lr))
            )
        ]
        # When every partner must change, all aim at the first line's rhyme, not at
        # each other's discarded originals: nice and street would chase each other.
        # The first line itself keeps its rhyme sound, and a rhyme word that has to
        # go (a forbidden final, the wrong ending) is nobody's target.
        head = members[0]
        anchors = settled
        if not anchors and head != ln.number and _rhyme_word_stays(variables[head].lr):
            anchors = [head]
        for k in anchors:
            current = _current(variables.get(k), lines[k] if partners_from_lines else None)
            t = current.tail if current else None
            if t is not None:
                rhyme_with.append(t.word)
                sound = sound or t.rime
                partner_ending = t.post if partner_ending is None else partner_ending
        if not anchors:
            if head == ln.number and lr.tail is not None and _rhyme_word_stays(lr):
                sound = lr.tail.rime
            moving = [k for k in members if k != ln.number and k in variables]
    syllables = rule.syllables_at(idx)
    want_ending = rule.ending_at(idx)
    if want_ending is None and partner_ending is not None:
        want_ending = min(partner_ending, 3)  # пустая asks тая: a feminine slot
    elif want_ending is None and lr.tail is not None and not line_errors(lr):
        want_ending = min(lr.tail.post, 3)  # a passing line keeps its own ending
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
    problems = [
        f"{i.message}" + (f" ({i.detail})" if i.detail else "")
        for i in lr.issues
        if i.severity == "error" or i.detail == REFRAIN
    ]
    problems.extend(b for b in var.blocked if b not in problems)
    if moving and not sound:
        names = ", ".join(f"L{k}" for k in moving)
        problems.append(f"{names} must change as well: any rhyme you can share will do")
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
        rejected=[f"{text} — {why}" for text, why in (var.rejected + _near_misses(var))[-8:]],
        copies=[k for k, src in _later_copies(variables).items() if src == ln.number],
        n=n,
    )
    if extra is not None:
        extra(var, req)
    return req


def _breaks_rhyme(lr: LineReport) -> bool:
    """Whether the line is one its rhyme group leaves out (day among night, light)."""
    return any(i.code == "rhyme" for i in lr.issues)


def _rhyme_word_stays(lr: LineReport) -> bool:
    """Whether a failing line may keep its last word: its errors are not about it."""
    return not any(i.code in ("final", "ending") for i in line_errors(lr))


def _near_misses(var: _Var) -> list[tuple[str, str]]:
    """Candidates that fit their own line but rhymed with no partner."""
    if var.chosen is not None:
        return []
    return [
        (c.text, "fits the line, but no partner rhymes with it") for c in var.pool if not c.original
    ]


def _current(var: _Var | None, original: LineReport | None) -> LineReport | None:
    """The partner line as it stands: its chosen or best candidate, else its text."""
    if var is None:
        return original
    best = var.chosen or max(var.pool, key=lambda c: c.weight, default=None)
    return best.report if best else original


def _trailing_asides(body: str) -> tuple[int, str, str] | None:
    """The backing vocals that end a line, read from its end: where they start,
    with the space before them; their text, (oh) (yeah) or (oh), (yeah); and the
    closing punctuation after them. None when the line ends on words."""

    def back(j: int, chars: str | None) -> int:  # past spaces, or past those chars
        while j > 0 and (body[j - 1].isspace() if chars is None else body[j - 1] in chars):
            j -= 1
        return j

    k = back(len(body), None)
    j = back(k, ASIDE_PUNCT)
    after, close, start = body[j:k], j, None
    while j > 0 and body[j - 1] == ")":
        o, depth = j - 1, 0
        while o >= 0:  # the ( that closes at j, past any nested pairs: (and (oh) yeah)
            depth += {")": 1, "(": -1}.get(body[o], 0)
            if depth == 0:
                break
            o -= 1
        if o < 0:
            break
        start = o
        j = back(back(o, None), ASIDE_PUNCT)  # (oh), (yeah): the comma between
        if j == 0 or body[j - 1] != ")":
            break
    if start is None:
        return None
    start = back(start, None)
    return start, body[start:close], after


def replace_lines(
    text: str, new: dict[int, str], lang: str | None = None, asides: bool = True
) -> str:
    """text with the given 1-based lines replaced, indentation and line endings kept.

    A line's closing punctuation stays when the new text has none, written the
    way lang writes it (the Armenian full stop is ։) when lang is given, and so
    does a backing vocal that ends it, unless the new text brings its own; the new
    line's own full stop then goes where the old one was, before or after it.
    With asides=False (a translation) the
    backing vocal, in the source's language, is left out.
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
            aside = _trailing_asides(body)
            if aside and "(" in content:
                lines[number - 1] = lead + content + ending
                continue
            if aside:
                body = body[: aside[0]]
            paren, after = aside[1:] if aside and asides else ("", "")
            own = PUNCT_RE.search(content)
            mark = PUNCT_RE.search(body)
            if own and paren and mark and not after:  # Բալիկ իմ, իմ գանձ։ (օրո՜ր)
                content += paren
            elif own and paren:  # I sing a lonely tune (oh baby).
                content = content[: own.start()] + paren + own.group(0).strip()
            elif not own:
                if mark:
                    tail = mark.group(0)
                    if lang is not None and tail.strip() in (".", "։", "՝"):  # not an ellipsis
                        tail = tail.translate(TO_ARMENIAN if lang == "hy" else FROM_ARMENIAN)
                    content += tail  # keep the line's closing comma or full stop
                content += paren + after
            lines[number - 1] = lead + content + ending
    return "".join(lines)
