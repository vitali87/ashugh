"""scan: analyze every line of a song and check it against a spec."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace

from . import lang as languages
from . import lyrics, meter, rhyme
from .meter import Fit
from .model import Line
from .spec import Rule, Spec, mixed_case

ENDING_NAMES = {0: "masculine", 1: "feminine", 2: "dactylic", 3: "hyperdactylic"}


@dataclass
class Issue:
    line: int
    code: str  # syllables | meter | feet | ending | final | rhyme | scheme | stress | script
    severity: str  # error | warning | info
    message: str
    detail: str = ""
    data: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "line": self.line,
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "detail": self.detail,
            **self.data,
        }


@dataclass
class LineReport:
    line: Line
    fit: Fit
    tails: list[rhyme.Tail]
    letter: str = ""
    target: int | None = None
    issues: list[Issue] = field(default_factory=list)
    min_rhyme: str = "near"  # its stanza's: a line is judged by its own rule
    alt_tails: list[rhyme.Tail] = field(default_factory=list)  # other readings a partner may pick

    @property
    def ok(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    @property
    def tail(self) -> rhyme.Tail | None:
        return self.tails[0] if self.tails else None

    @property
    def sung(self) -> str:
        parts = []
        for i, w in enumerate(self.line.words):
            stress = self.fit.stresses.get(i, w.stress_options()[0])
            text = w.sung(stress, mark=w.lang == "ru")
            if i in self.fit.elided and w.drop is not None:
                syls = [s.text for s in w.syllables]
                syls[w.drop] = syls[w.drop].replace("ը", "(ը)", 1).replace("Ը", "(Ը)", 1)
                text = "-".join(syls)
            parts.append(text)
        return " ".join(p for p in parts if p)

    @property
    def ending(self) -> str:
        return ENDING_NAMES.get(self.fit.ending, f"{self.fit.ending} after stress")


@dataclass
class UnitReport:
    section: str
    key: str
    meter: str
    meter_source: str  # spec | detected
    scheme: str
    rule: Rule
    lines: list[LineReport]
    scope: str | None = None  # stanzas sharing one rhyme scheme ("ABBA ABBA CDC DCD")


@dataclass
class Report:
    path: str
    spec: Spec
    units: list[UnitReport]
    text: str = ""  # the lyrics as scanned

    @property
    def lines(self) -> list[LineReport]:
        return [lr for u in self.units for lr in u.lines]

    @property
    def issues(self) -> list[Issue]:
        found = [i for lr in self.lines for i in lr.issues]
        return sorted(found, key=lambda i: (i.line, i.code))

    def count(self, severity: str) -> int:
        return sum(1 for i in self.issues if i.severity == severity)

    @property
    def ok(self) -> bool:
        return self.count("error") == 0

    @property
    def languages(self) -> list[str]:
        seen = []
        for lr in self.lines:
            if lr.line.lang and lr.line.lang not in seen:
                seen.append(lr.line.lang)
        return seen


def _quote(text: str) -> str:
    return f"«{text}»"


def analyze_lines(text: str, spec: Spec, forced: str | None = None) -> list[Line]:
    lines = lyrics.parse(text)
    tokens = [lyrics.tokenize(ln.text) for ln in lines]
    default = forced or spec.language or languages.detect([t for ts in tokens for t in ts])
    for ln, ts in zip(lines, tokens):
        ln.lang = forced or spec.language or languages.detect(ts) or default
        ln.words = languages.analyze(ln.lang, ts, spec.lexicon, ln.text)
    return lines


def scan(text: str, spec: Spec | None = None, path: str = "-", lang: str | None = None) -> Report:
    spec = spec or Spec()
    lines = analyze_lines(text, spec, lang)
    units: dict[int, list[Line]] = {}
    for ln in lines:
        units.setdefault(ln.unit, []).append(ln)
    report = Report(path, spec, [], text)
    stanzas = list(units.values())
    rules, scopes, short = _shared_schemes(stanzas, spec, text)
    for unit_lines, rule, scope in zip(stanzas, rules, scopes):
        report.units.append(_scan_unit(unit_lines, rule, scope))
    _check_shared_rhymes(report.units)
    for k, have, parts in short:
        lr = report.units[k].lines[-1]
        lr.issues.append(
            Issue(
                lr.line.number,
                "scheme",
                "warning",
                f"{have} stanzas, rhyme {' '.join(parts)} wants {len(parts)}",
            )
        )
    return report


def _shared_schemes(stanzas: list[list[Line]], spec: Spec, text: str):
    """Each stanza's rule, with a spaced scheme ("ABBA ABBA CDC DCD") dealt out
    over a run of stanzas that share it; the run's stanzas get one scope, so
    their letters name the same rhymes. A tag starts the scheme over, a
    scheme longer than the run repeats with fresh rhymes, and a run that ends
    partway through the scheme is reported in short as (last stanza, stanzas
    in the cycle, parts)."""
    rules = [spec.rule_for(u[0].key, u[0].unit) for u in stanzas]
    scopes: list[str | None] = [None] * len(stanzas)
    short: list[tuple[int, int, tuple[str, ...]]] = []
    tags = [n for n, raw in enumerate(lyrics.split_lines(text), 1) if lyrics.TAG_RE.match(raw)]

    def joined(a: list[Line], b: list[Line]) -> bool:
        return not any(a[-1].number < n < b[0].number for n in tags)

    k = 0
    while k < len(stanzas):
        end, parts = k, rules[k].rhyme_parts
        while (  # a [stanza.N] table that leaves the rhyme alone stays in the run
            parts
            and end + 1 < len(stanzas)
            and rules[end + 1].rhyme_parts == parts
            and joined(stanzas[end], stanzas[end + 1])
        ):
            end += 1
        if end > k:
            n = len(parts)
            for j in range(end - k + 1):
                rules[k + j] = _part_rule(rules[k + j], parts[j % n])
                scopes[k + j] = f"{k}:{j // n}"
            if (end - k + 1) % n:
                short.append((end, (end - k + 1) % n, parts))
        k = end + 1
    return rules, scopes, short


def _part_rule(rule: Rule, part: str) -> Rule:
    """A stanza's share of a spaced scheme. When the whole scheme mixes cases,
    a part in one case still asks its endings: CDC in AbbA AbbA CDC DCD."""
    endings = rule.endings
    if endings is None and rule.rhyme and mixed_case(rule.rhyme):
        endings = "".join("f" if c.isupper() else "m" if c.islower() else "-" for c in part)
    return replace(rule, rhyme=part, rhyme_parts=(), endings=endings)


def _check_shared_rhymes(units: list[UnitReport]) -> None:
    """Check the rhyme groups that run across the stanzas of one spaced scheme."""
    scoped: dict[str, list[UnitReport]] = {}
    for u in units:
        if u.scope is not None:
            scoped.setdefault(u.scope, []).append(u)
    for members in scoped.values():
        for u in members:  # stresses chosen with the partners in other stanzas
            partners: dict[int, list[list[rhyme.Tail]]] = {}
            for v in members:
                if v is u:
                    continue
                for lr in v.lines:
                    g = v.rule.rhyme_at(lr.line.index)
                    for mine in u.lines:
                        if g is not None and u.rule.rhyme_at(mine.line.index) == g:
                            partners.setdefault(mine.line.number, []).append(lr.tails)
            _finish(u, partners, groups=False)
        groups: dict[str, list[LineReport]] = {}
        for u in members:
            for g, lrs in _groups(u.lines, u.rule).items():
                groups.setdefault(g, []).extend(lrs)
        _check_groups(groups)
        letters = rhyme.scheme([lr.tails for u in members for lr in u.lines])
        for u in members:  # one lettering for the stanzas that share a scheme
            u.scheme, letters = letters[: len(u.lines)], letters[len(u.lines) :]
            for lr, letter in zip(u.lines, u.scheme):
                lr.letter = letter


def _scan_unit(lines: list[Line], rule: Rule, scope: str | None = None) -> UnitReport:
    first = lines[0]
    if rule.meter:
        meter_name, source = rule.meter, "spec"
    else:
        meter_name, source = meter.detect(lines), "detected"
    reports = [check_line(ln, rule, meter_name, source) for ln in lines]
    unit = UnitReport(first.section, first.key, meter_name, source, "", rule, reports, scope)
    if scope is None:  # a shared scheme is finished once all its stanzas are read
        _finish(unit, {}, groups=True)
    return unit


def _finish(unit: UnitReport, others: dict[int, list[list[rhyme.Tail]]], groups: bool) -> None:
    """Choose rhyme stresses, letter the stanza and check its scheme."""
    _rhyme_stress(unit.lines, unit.rule, unit.meter, unit.meter_source, others)
    unit.scheme = rhyme.scheme([lr.tails for lr in unit.lines])
    for lr, letter in zip(unit.lines, unit.scheme):
        lr.letter = letter
    _check_rhyme(unit.lines, unit.rule, groups)


def check_line(
    ln: Line,
    rule: Rule,
    meter_name: str,
    source: str,
    force: dict | None = None,
    promote: bool | None = None,
) -> LineReport:
    """Fit one analyzed line to its slot and collect its line-level issues."""
    target = rule.syllables_at(ln.index)
    feet = rule.feet_at(ln.index)
    f = meter.fit(ln.words, meter_name, target, rule.tolerance, force, feet, promote)
    lr = LineReport(ln, f, rhyme.tails(ln, f), target=target, min_rhyme=rule.min_rhyme)
    _check_line(lr, rule, meter_name, source)
    return lr


RHYME_STRESS_MARGIN = 0.6  # extra meter cost a stress may take to make a rhyme
RHYME_STRESS_GAIN = 0.15  # how much better the rhyme must get


def _rhyme_stress(
    reports: list[LineReport],
    rule: Rule,
    meter_name: str,
    source: str,
    beyond: Mapping[int, list[list[rhyme.Tail]]] | None = None,
) -> None:
    """Let rhymes choose the stress of ambiguous line-final words (облака́ / издалека́),
    or put an English line's last beat on its final syllable (memory / free).

    The meter alone often cannot tell о́блака from облака́. When another reading
    of a line's rhyme word costs the meter little more and rhymes clearly better
    with a line of the same stanza (or a partner in the stanzas sharing its
    scheme: beyond, by line number), that reading wins.
    """
    floor = rhyme.THRESHOLD["near"]
    for _ in range(2):
        changed = False
        for k, lr in enumerate(reports):
            tries = _rhyme_tries(lr)
            if not tries:
                continue
            others = [r.tails for m, r in enumerate(reports) if m != k]
            others += (beyond or {}).get(lr.line.number, [])
            if not others:
                return

            def best(tails, others=others) -> float:
                return max((rhyme.match(tails, t)[0] for t in others), default=0.0)

            current = best(lr.tails)
            for force, promote in tries:
                alt = check_line(lr.line, rule, meter_name, source, force, promote)
                if not _affordable(alt, lr):
                    continue
                score = best(alt.tails)
                if score >= floor and score > current + RHYME_STRESS_GAIN:
                    reports[k], current, lr, changed = alt, score, alt, True
        if not changed:
            return


def _rhyme_tries(lr: LineReport) -> list[tuple[dict[int, int | None] | None, bool | None]]:
    """The other readings of a line's rhyme word to try: its other stresses, and for
    English a beat on the last syllable."""
    w = rhyme.anchor_word(lr.line, lr.fit)
    if w is None:
        return []
    word = lr.line.words[w]
    tries: list[tuple[dict[int, int | None] | None, bool | None]] = [
        ({w: option}, None)
        for option in word.stress_options()
        if word.ambiguous and option not in (None, lr.fit.stresses.get(w))
    ]
    if word.lang == "en" and not lr.fit.promoted:
        tries.append((None, True))
    return tries


def _affordable(alt: LineReport, lr: LineReport) -> bool:
    """Whether a rhyme may choose alt over lr: little more meter cost, the same
    length, and no error a rhyme cannot buy (feet, ending)."""
    return (
        alt.fit.cost - lr.fit.cost <= RHYME_STRESS_MARGIN
        and alt.fit.count == lr.fit.count
        and _errors(alt) <= _errors(lr)
    )


def rhyme_alternatives(lr: LineReport, rule: Rule, meter_name: str, source: str) -> list:
    """The rhyme tails a line could also take if a partner asked for them: облака́
    for a line the meter alone reads with о́блака."""
    out: list[rhyme.Tail] = []
    for force, promote in _rhyme_tries(lr):
        alt = check_line(lr.line, rule, meter_name, source, force, promote)
        if _affordable(alt, lr):
            out += [t for t in alt.tails if t not in lr.tails and t not in out]
    return out


def _errors(lr: LineReport) -> int:
    return sum(1 for i in lr.issues if i.severity == "error")


def reanalyze(ln: Line, text: str, spec: Spec, lang: str | None = None) -> Line:
    """A copy of ln holding text instead, analyzed in the same slot."""
    tokens = lyrics.tokenize(text)
    code = lang or spec.language or languages.detect(tokens) or ln.lang
    new = Line(ln.number, text.strip(), ln.section, ln.key, ln.unit, ln.index, code)
    new.words = languages.analyze(code, tokens, spec.lexicon, text)
    return new


def _hidden_vowels(ln: Line) -> str:
    shown = [w for w in ln.words if any(s.epenthetic for s in w.syllables)]
    return ", ".join(f"{_quote(w.text)} sings as {w.sung()}" for w in shown[:3])


def _check_line(lr: LineReport, rule: Rule, meter_name: str, source: str) -> None:
    ln, f = lr.line, lr.fit
    add = lr.issues.append

    foreign = [w for w in ln.words if w.lang == "xx"]
    if foreign:
        names = ", ".join(_quote(w.text) for w in foreign[:4]) + (
            " ..." if len(foreign) > 4 else ""
        )
        add(
            Issue(
                ln.number,
                "script",
                "warning",
                "not Armenian, Russian or English",
                f"{names}: syllables counted by vowel groups, stress unknown",
            )
        )
    if lyrics.has_digits(ln.text):
        add(Issue(ln.number, "script", "warning", "digits are not counted", "spell numbers out"))
    for i, w in enumerate(ln.words):
        if w.lang == "xx":
            continue
        if w.guessed and w.size > 1:
            st = f.stresses.get(i)
            add(
                Issue(
                    ln.number,
                    "stress",
                    "warning",
                    f"stress of {_quote(w.text)} unknown",
                    f"assumed {w.sung(st, mark=True)}; add it to [lexicon] if wrong",
                    {"word": w.text, "assumed": st},
                )
            )
        elif w.ambiguous and meter_name != "free" and w.size > 1:
            st = f.stresses.get(i)
            add(
                Issue(
                    ln.number,
                    "stress",
                    "info",
                    f"{_quote(w.text)} read as {w.sung(st, mark=True)}",
                    "stress is ambiguous; the meter picked this reading",
                    {"word": w.text, "assumed": st},
                )
            )

    if lr.target is not None:
        miss = f.count - lr.target
        if abs(miss) > rule.tolerance:
            detail = _hidden_vowels(ln) if miss > 0 else ""
            add(
                Issue(
                    ln.number,
                    "syllables",
                    "error",
                    f"{f.count} syllable{'s' if f.count != 1 else ''}, slot is {lr.target}",
                    detail,
                    {"expected": lr.target, "actual": f.count},
                )
            )
        else:
            for i in sorted(f.elided):
                w = ln.words[i]
                if w.lang == "hy" and w.drop == w.optional:
                    what = "drops its ը"
                    detail = "speech often leaves out the ը of a compound's second root"
                elif w.lang == "hy":
                    how = (
                        "merges into the vowel before it"
                        if w.drop == 0
                        else "links its last consonant to the vowel after it"
                    )
                    what, detail = "drops its ը", f"in connected speech the word {how}"
                else:
                    what = "is sung with one syllable fewer"
                    detail = f"{w.sung()} also has a shorter pronunciation"
                add(
                    Issue(
                        ln.number, "syllables", "info", f"fits if {_quote(w.text)} {what}", detail
                    )
                )

    if source == "spec" and meter_name != "free" and (f.off_beat or f.ending_off):
        names = [_quote(ln.words[i].sung(f.stresses.get(i), mark=True)) for i in f.off_beat]
        if names:
            what = f"{', '.join(names[:3])}{' ...' if len(names) > 3 else ''} off the beat"
        else:
            what = "last stress off the beat"
        add(
            Issue(
                ln.number,
                "meter",
                "error",
                what,
                f"stress {f.grid}, {meter_name} wants {f.template}",
                {
                    "words": [ln.words[i].text for i in f.off_beat],
                    "grid": f.grid,
                    "template": f.template,
                },
            )
        )

    if source == "spec" and meter_name != "free":
        feet = rule.feet_at(ln.index)
        if feet is not None and f.feet != feet:
            need = meter.length(meter_name, feet, f.ending)
            detail = f"{f.grid} as {meter_name}"
            if need is not None and lr.target is None:
                detail = (
                    f"{f.count} syllables; {meter_name}{feet} with a {lr.ending} ending has {need}"
                )
            add(
                Issue(
                    ln.number,
                    "feet",
                    "error",
                    f"{f.feet} feet, slot is {feet}",
                    detail,
                    {"expected": feet, "actual": f.feet},
                )
            )

    want = rule.ending_at(ln.index)
    if want is not None and f.ending != want:
        add(
            Issue(
                ln.number,
                "ending",
                "error",
                f"ends {lr.ending}, slot is {ENDING_NAMES.get(want, want)}",
                _quote(ln.words[-1].text) if ln.words else "",
                {"expected": ENDING_NAMES.get(want), "actual": lr.ending},
            )
        )

    if rule.forbid_final and ln.words:
        last = ln.words[-1].norm
        for suffix in rule.forbid_final:
            if last.endswith(suffix):
                add(
                    Issue(
                        ln.number,
                        "final",
                        "error",
                        f"ends in {suffix}",
                        f'forbid_final = ["{suffix}"]',
                        {"word": ln.words[-1].text},
                    )
                )
                break


def _check_rhyme(reports: list[LineReport], rule: Rule, groups: bool = True) -> None:
    if not rule.rhyme:
        return
    n = len(rule.rhyme)
    if len(reports) < n:
        lr = reports[-1]
        lr.issues.append(
            Issue(
                lr.line.number,
                "scheme",
                "warning",
                f"stanza has {len(reports)} lines, rhyme {rule.rhyme} wants {n}",
            )
        )
    if groups:
        _check_groups(_groups(reports, rule))


def _groups(reports: list[LineReport], rule: Rule) -> dict[str, list[LineReport]]:
    out: dict[str, list[LineReport]] = {}
    for lr in reports:
        g = rule.rhyme_at(lr.line.index)
        if g is not None:
            out.setdefault(g, []).append(lr)
    return out


def _check_groups(groups: dict[str, list[LineReport]]) -> None:
    for g, members in groups.items():
        head = members[0]
        for lr in members[1:]:
            s, ta, tb = rhyme.match(head.tails, lr.tails)
            if s >= rhyme.THRESHOLD[lr.min_rhyme]:
                continue
            a = ta.word if ta else head.line.text
            b = tb.word if tb else lr.line.text
            lr.issues.append(
                Issue(
                    lr.line.number,
                    "rhyme",
                    "error",
                    f"rhyme {g[0]} broken",
                    f"{_quote(a)} / {_quote(b)}: {rhyme.level(s)} {s:.2f}, need {lr.min_rhyme}",
                    {
                        "group": g[0],
                        "with_line": head.line.number,
                        "score": s,
                        "level": rhyme.level(s),
                    },
                )
            )
