"""scan: analyze every line of a song and check it against a spec."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field, replace

from . import lang as languages
from . import lyrics, meter, rhyme
from .lang import en
from .meter import Fit
from .model import Line, mark_stress
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
        words = self.line.words
        for i, w in enumerate(words):
            stress = self.fit.stresses.get(i, w.stress_options()[0])
            part = w.sung(stress, mark=w.lang == "ru", dropped=i in self.fit.elided)
            nxt = i + 1
            if w.lang == "ru" and nxt < len(words) and words[nxt].leans:
                if self.fit.stresses.get(nxt, 0) is None:  # за́ город: the noun gave it
                    part = mark_stress(part)
            parts.append(part)
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


def _count(n: int, one: str, many: str = "") -> str:
    """1 line, 2 lines; 1 foot, 3 feet."""
    return f"{n} {one if n == 1 else many or one + 's'}"


def _quote(text: str) -> str:
    return f"«{text}»"


def analyze_lines(text: str, spec: Spec, forced: str | None = None) -> list[Line]:
    lines = lyrics.parse(lyrics.clean(text))
    tokens = [lyrics.tokenize(ln.text) for ln in lines]
    default = forced or spec.language or languages.detect([t for ts in tokens for t in ts])
    if not forced and not spec.language and default == "en":
        # Ari u el mi gna: a song mostly in Armenian typed in Latin letters is Armenian
        typed = [languages.latin_armenian(ts) for ts in tokens if ts]
        if len(typed) >= 2 and 2 * sum(typed) > len(typed):
            default = "hy"
    for ln, ts in zip(lines, tokens):
        detected = languages.detect(ts)
        if default == "hy" and detected == "en" and languages.latin_armenian(ts):
            detected = "hy"  # Mtnem qo srtin in an Armenian song: Armenian typed in Latin
        ln.lang = forced or spec.language or detected or default
        ln.words = languages.analyze(ln.lang, ts, spec.lexicon, ln.text)
    return lines


def scan(text: str, spec: Spec | None = None, path: str = "-", lang: str | None = None) -> Report:
    spec = spec or Spec()
    text = lyrics.clean(text)
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
    _check_spec_tables(report)
    return report


def _check_spec_tables(report: Report) -> None:
    """A [section.X] or [stanza.N] that matches nothing is likely a typo: chorsu."""
    if not report.lines:
        return
    first = report.lines[0]
    keys = {lr.line.key for lr in report.lines} | lyrics.section_keys(report.text)  # [Intro] (о-о)
    found = [
        (f"[section.{name}] matches no section of the song", ", ".join(sorted(keys - {""})))
        for name in sorted(report.spec.sections)
        if name not in keys
    ]
    count = len(report.units)
    found += [
        (f"[stanza.{n}] is past the song's {count} stanzas", "")
        for n in sorted(report.spec.stanza_tables)
        if n > count
    ]
    for message, detail, lr in _impossible_slots(report):  # on the stanza that asks it
        lr.issues.append(Issue(lr.line.number, "spec", "warning", message, detail))
    tables = report.spec.stanza_tables
    if tables and report.spec.base.empty and not report.spec.sections:
        found += [
            (f"stanza {n} has no rules", f"the spec's [stanza.N] tables stop at {max(tables)}")
            for n in range(max(tables) + 1, count + 1)
        ]
    for message, detail in found:
        first.issues.append(Issue(first.line.number, "spec", "warning", message, detail))


def _impossible_slots(report: Report) -> list[tuple[str, str, LineReport]]:
    """Slots no line can fill (8 syllables of iamb4 with a feminine ending, which
    has 9), each with the first line that has it."""
    out: list[tuple[str, str, LineReport]] = []
    for unit in report.units:
        rule = unit.rule
        if not rule.meter or not rule.syllables:
            continue
        name, meter_feet = meter.parse_meter(rule.meter)
        for lr in unit.lines:
            i = lr.line.index
            feet = rule.feet_at(i) or meter_feet
            ending, syllables = rule.ending_at(i), rule.syllables_at(i)
            if feet is None or ending is None or syllables is None:
                continue
            need = meter.length(name, feet, ending)
            english = any(w.lang == "en" for w in lr.line.words)
            fewest = meter.shortest(name, feet, ending, english)
            if need is None or fewest is None:
                continue
            if fewest - rule.tolerance <= syllables <= need + rule.tolerance:
                continue
            message = (
                f"the spec asks {syllables} syllables of {name}{feet} with a "
                f"{ENDING_NAMES[ending]} ending, which has {need}"
            )
            if all(m != message for m, _, _ in out):
                detail = "no line can pass this slot; change the count or the ending"
                out.append((message, detail, lr))
    return out


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
    tags = [n for n, raw in enumerate(lyrics.split_lines(text), 1) if lyrics.is_tag(raw)]

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
        letters = rhyme.scheme(
            [lr.tails for u in members for lr in u.lines], _floor(members[0].rule)
        )
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


def _floor(rule: Rule) -> float:
    """The rhyme a spec asks for, below which no lines are lettered alike: its
    min_rhyme where it sets a scheme, near otherwise."""
    return rhyme.THRESHOLD[rule.min_rhyme] if rule.rhyme else rhyme.THRESHOLD["near"]


def _finish(unit: UnitReport, others: dict[int, list[list[rhyme.Tail]]], groups: bool) -> None:
    """Choose rhyme stresses, letter the stanza and check its scheme."""
    _rhyme_stress(unit.lines, unit.rule, unit.meter, unit.meter_source, others)
    unit.scheme = rhyme.scheme([lr.tails for lr in unit.lines], _floor(unit.rule))
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
    want = rule.ending_at(ln.index)
    last = ln.words[-1] if ln.words else None
    if (
        target is None
        and want is not None
        and f.ending == want + 1
        and last is not None
        and last.drop == last.size - 1
        and len(ln.words) - 1 not in f.elided
    ):
        # fire, hour, poem: a last word sung a syllable short gives the asked ending
        short = meter.fit(ln.words, meter_name, f.count - 1, 0, force, feet, promote)
        if short.ending == want and short.count == f.count - 1:
            f = short
    tails = [] if ends_in_number(ln.text) else rhyme.tails(ln, f)  # in '99: no rhyme on in
    lr = LineReport(ln, f, tails, target=target, min_rhyme=rule.min_rhyme)
    _check_line(lr, rule, meter_name, source)
    return lr


STAGE_RE = re.compile(r"\*[^*\n]+\*")  # *spoken*, *whispers*
LAST_NUMBER_RE = re.compile(r"\d[^\w]*$")


def ends_in_number(text: str) -> bool:
    """Whether a line's last sung token is written in digits: born in '99."""
    return bool(LAST_NUMBER_RE.search(lyrics.sub_asides(text, lambda _: "").rstrip()))


DIGITS = "digits are not counted"  # a warning to a reader, an error to a repair
ROMAN_RE = re.compile(r"(?=[MDCLXVI])M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})")
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
    floor = _floor(rule)
    # what each line could also be, so two ambiguous partners can move together:
    # у́тра / о́строва both become утра́ / острова́
    could = [rhyme_alternatives(r, rule, meter_name, source) for r in reports]
    for _ in range(2):
        changed = False
        for k, lr in enumerate(reports):
            tries = _rhyme_tries(lr)
            if not tries:
                continue
            others = [r.tails + could[m] for m, r in enumerate(reports) if m != k]
            others += (beyond or {}).get(lr.line.number, [])
            if not others:
                return

            def best(tails, others=others) -> float:
                return max((rhyme.match(tails, t)[0] for t in others), default=0.0)

            # in free verse a line's tails hold every reading; judge the one it shows
            current = best(rhyme.tails(lr.line, lr.fit, chosen_only=True))
            for force, promote in tries:
                alt = check_line(lr.line, rule, meter_name, source, force, promote)
                # a scheme the spec declares outranks a meter it never asked for
                if not _affordable(alt, lr, source == "detected" and bool(rule.rhyme)):
                    continue
                score = best(rhyme.tails(alt.line, alt.fit, chosen_only=True))
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
    if word.leans and lr.fit.stresses.get(w) is not None:
        tries.append(({w: None}, None))  # по́ лесу / по́ голосу
    if word.lang == "en" and not lr.fit.promoted:
        tries.append((None, True))
    return tries


def _affordable(alt: LineReport, lr: LineReport, any_cost: bool = False) -> bool:
    """Whether a rhyme may choose alt over lr: little more meter cost (any, for a
    rhyme the spec declares under a meter only detected: холодные во́ды / годы),
    the same length, and no error a rhyme cannot buy (feet, ending)."""
    return (
        (any_cost or alt.fit.cost - lr.fit.cost <= RHYME_STRESS_MARGIN)
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
    text = lyrics.clean(text)
    tokens = lyrics.tokenize(text)
    code = lang or spec.language or languages.detect(tokens) or ln.lang
    new = Line(ln.number, text.strip(), ln.section, ln.key, ln.unit, ln.index, code)
    new.words = languages.analyze(code, tokens, spec.lexicon, text)
    return new


def _elision_notes(ln: Line, f, add, source: str = "spec") -> None:
    """Notes on the syllables the line's fit leaves out, so none goes unsaid; for
    English only where a spec holds the line, and not for a word whose short form
    is its usual one (real)."""
    for i in sorted(f.elided):
        w = ln.words[i]
        if w.lang == "en" and (source != "spec" or w.drop_cost < 0):
            continue
        if w.lang == "hy" and w.drop == w.optional:
            what = "drops its ը"
            detail = w.optional_why
        elif w.lang == "hy":
            how = (
                "merges into the vowel before it"
                if w.drop == 0
                else "links its last consonant to the vowel after it"
            )
            what, detail = "drops its ը", f"in connected speech the word {how}"
        else:
            what = "is sung with one syllable fewer"
            short = "-".join(en.sung_pieces([x.text for x in w.syllables], w.drop, True))
            detail = f"sung {short}, {_count(w.size - 1, 'syllable')}"
        add(Issue(ln.number, "syllables", "info", f"fits if {_quote(w.text)} {what}", detail))


def _hidden_vowels(ln: Line, elided: frozenset[int]) -> str:
    """The words whose unwritten ը the count includes: not one the line already drops."""
    shown = [
        f"{_quote(w.text)} sings as {w.sung(dropped=i in elided)}"
        for i, w in enumerate(ln.words)
        if any(
            s.epenthetic and not (i in elided and k == w.drop) for k, s in enumerate(w.syllables)
        )
    ]
    return ", ".join(shown[:3])


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
                f"{names}: syllables counted by vowel groups, stress and rhyme unknown",
            )
        )
    if lyrics.has_digits(ln.text):
        add(Issue(ln.number, "script", "warning", DIGITS, "spell numbers out"))
    roman = [w.text for w in ln.words if ln.lang != "en" and ROMAN_RE.fullmatch(w.text)]
    if roman:  # XXI դար, Пётр I: sung as letters, not as the number
        detail = f"{', '.join(roman)}: spell the number out"
        add(Issue(ln.number, "script", "warning", "a Roman numeral is sung as letters", detail))
    outside = lyrics.sub_asides(ln.text, lambda _: " ")
    if "(" in outside or ")" in outside:  # I walk alone (and cry
        detail = "a backing vocal goes in (…) closed on its line; these words are counted"
        add(Issue(ln.number, "tag", "warning", "an unclosed parenthesis", detail))
    if STAGE_RE.search(outside):  # *spoken*: Suno sings it
        detail = "a direction goes in a tag such as [Spoken]; these words are counted"
        add(Issue(ln.number, "tag", "warning", "a direction in asterisks", detail))
    if any(ch in "[]" for ch in outside):  # [Bridge] I walk
        detail = "a tag such as [Chorus] goes on a line of its own; these words are counted"
        add(Issue(ln.number, "tag", "warning", "brackets in a sung line", detail))
    warned: set[str] = set()  # a word guessed twice in a line is named once
    for i, w in enumerate(ln.words):
        if w.lang == "xx":
            continue
        if w.guessed and w.size == 1 and w.lang == "en":
            # Russian and Armenian count a word's syllables by its vowels; English
            # spelling does not (zorb, gnaw, Ngozi), so a guessed one is named too.
            if w.norm not in warned:
                warned.add(w.norm)
                add(
                    Issue(
                        ln.number,
                        "stress",
                        "warning",
                        f"{_quote(w.text)} unknown",
                        "counted as one syllable from its spelling; add it to [lexicon] if wrong",
                        {"word": w.text},
                    )
                )
        elif w.guessed and w.size > 1:
            if w.norm in warned:
                continue
            warned.add(w.norm)
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
        elif (
            meter_name != "free"
            and w.size > 1
            and (w.ambiguous or (f.stresses.get(i) is None and w.leans and len(w.readings) > 1))
        ):
            st = f.stresses.get(i)
            shown = _quote(w.text), w.sung(st, mark=True)
            if st is None and w.leans and i > 0:  # the preposition took the stress
                prep = ln.words[i - 1]
                shown = _quote(f"{prep.text} {w.text}"), f"{mark_stress(prep.text)} {w.sung()}"
            add(
                Issue(
                    ln.number,
                    "stress",
                    "info",
                    f"{shown[0]} read as {shown[1]}",
                    "stress is ambiguous; the meter picked this reading",
                    {"word": w.text, "assumed": st},
                )
            )

    if lr.target is not None:
        miss = f.count - lr.target
        if abs(miss) > rule.tolerance:
            detail = _hidden_vowels(ln, f.elided) if miss > 0 else ""
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
            _elision_notes(ln, f, add)  # the spec's count asks for it
    elif f.elided:
        _elision_notes(ln, f, add, source)  # the meter dropped it: Eve-ry heartbeat

    if source == "spec" and meter_name != "free" and (f.off_beat or f.ending_off):
        names = [  # as the line sings them: ev-ry when its note says so
            _quote(ln.words[i].sung(f.stresses.get(i), mark=True, dropped=i in f.elided))
            for i in f.off_beat
        ]
        if names:
            what = f"{', '.join(names[:3])}{' ...' if len(names) > 3 else ''} off the beat"
        else:
            what = "last stress off the beat"
        feet = rule.feet_at(ln.index)
        own = min(lr.tail.post, 3) if lr.tail is not None else f.ending
        slot = meter.slot_template(meter_name, feet, own) if feet is not None else None
        if slot is not None and lr.target is None and f.feet == feet and len(slot) != f.count:
            # the beats were forced onto the slot's feet: the line is the wrong length
            english = any(w.lang == "en" for w in ln.words)
            fewest = meter.shortest(meter_name, feet, own, english) or len(slot)
            if not fewest <= f.count <= len(slot):
                add(
                    Issue(
                        ln.number,
                        "syllables",
                        "error",
                        f"{f.count} syllables, slot is {len(slot)}",
                        f"{meter_name}{feet} with a {ENDING_NAMES[own]} ending has {len(slot)}",
                        {"expected": len(slot), "actual": f.count},
                    )
                )
        wants = f"{meter_name}{feet} wants {slot}" if slot else f"{meter_name} wants {f.template}"
        add(
            Issue(
                ln.number,
                "meter",
                "error",
                what,
                f"stress {f.grid}, {wants}",
                {
                    "words": [ln.words[i].text for i in f.off_beat],
                    "at": list(f.off_beat),  # word indices, for an editor to underline
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
                    f"{_count(f.feet, 'foot', 'feet')}, slot is {feet}",
                    detail,
                    {"expected": feet, "actual": f.feet},
                )
            )

    want = rule.ending_at(ln.index)
    if want is not None and f.ending != want and not (want == 3 and f.ending > 3):  # h: 3 or more
        detail = _quote(ln.words[-1].text) if ln.words else ""
        letter = rule.rhyme[ln.index % len(rule.rhyme)] if rule.rhyme and not rule.endings else ""
        if letter.isalpha():  # AbAb: a capital letter asks a feminine ending, a small one masculine
            case = "capital" if letter.isupper() else "small"
            detail += f"; the rhyme's {case} {letter} asks {ENDING_NAMES.get(want, want)}"
        add(
            Issue(
                ln.number,
                "ending",
                "error",
                f"ends {lr.ending}, slot is {ENDING_NAMES.get(want, want)}",
                detail,
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
                f"stanza has {_count(len(reports), 'line')}, rhyme {rule.rhyme} wants {n}",
            )
        )
    elif groups and len(reports) > n:
        _short_scheme(reports, rule.rhyme)
    if groups:
        _check_groups(_groups(reports, rule))


def _short_scheme(reports: list[LineReport], scheme: str) -> None:
    """A scheme shorter than its stanza starts over with new rhymes, as AABB on
    eight lines is AABBCCDD. Warn where that leaves rhymes the writer likely
    meant unchecked: AB on four lines names each letter once, so no line must
    rhyme (ABAB says A and A rhyme), and ABAB on six leaves lines 5 and 6
    with no partner."""
    size, n = len(reports), len(scheme)
    letters = [c.upper() for c in scheme if c.isalpha()]
    message = detail = ""
    if letters and len(set(letters)) == len(letters):
        message = f"rhyme {scheme} names each letter once: on {size} lines no line must rhyme"
        detail = f"for rhymes across the stanza write them out: {scheme * (size // n)}"
    elif size % n:
        part = [c.upper() for c in scheme[: size % n] if c.isalpha()]
        alone = [c for c in part if part.count(c) == 1 and letters.count(c) > 1]
        if alone:
            message = f"stanza has {_count(size, 'line')}, rhyme {scheme} fits {n}"
            detail = f"the last {size % n} start it over, where {alone[0]} has no partner"
    if message:
        lr = reports[-1]
        lr.issues.append(Issue(lr.line.number, "scheme", "warning", message, detail))


def _groups(reports: list[LineReport], rule: Rule) -> dict[str, list[LineReport]]:
    out: dict[str, list[LineReport]] = {}
    for lr in reports:
        g = rule.rhyme_at(lr.line.index)
        words = lr.line.words
        if g is None or (words and words[-1].lang == "xx"):  # a script not read
            continue
        if ends_in_number(lr.line.text):  # its rhyme is a number ashugh does not read
            continue
        out.setdefault(g, []).append(lr)
    return out


def _check_groups(groups: dict[str, list[LineReport]]) -> None:
    """A group holds where its lines rhyme with one another, each pair judged by
    the later line's min_rhyme: the largest such set stands (the first line's on
    a tie), and every line outside it is broken, shown with the member it comes
    closest to. cup / end / friends / ends breaks at cup."""
    for g, members in groups.items():
        kept, pair = rhyming_set(members)
        for k, lr in enumerate(members):
            if k in kept:
                _same_word(members, k, pair)
                continue
            partner = max(sorted(kept), key=lambda m: pair(m, k)[0])
            s, ta, tb = pair(partner, k)
            other = members[partner]
            near = rhyme.match(_any_reading(other), _any_reading(lr))
            if s < near[0] < rhyme.THRESHOLD[lr.min_rhyme]:
                s, ta, tb = near  # стене́ / голове́ slant, not a rare сте́не's none
            a, b = (ta.word if ta else other.line.text), (tb.word if tb else lr.line.text)
            if partner > k:
                a, b = b, a
            lr.issues.append(
                Issue(
                    lr.line.number,
                    "rhyme",
                    "error",
                    f"rhyme {g[0]} broken",
                    f"{_quote(a)} / {_quote(b)}: {rhyme.level(s)} {s:.2f}, need {lr.min_rhyme}",
                    {
                        "group": g[0],
                        "with_line": other.line.number,
                        "score": s,
                        "level": rhyme.level(s),
                    },
                )
            )


def _any_reading(lr: LineReport) -> list[rhyme.Tail]:
    """The tails of every reading of a line's rhyme words, whatever the meter says."""
    return rhyme.tails(lr.line, meter.free_fit(lr.line.words))


REFRAIN = "the same word is a refrain, not a rhyme; fine if meant"


def _same_word(members: list[LineReport], k: int, pair) -> None:
    """A line rhyming only on the word an earlier one ends with, or on another form
    of it (сердце / сердца): a refrain, which may be meant, but no rhyme. A line
    repeated whole is a refrain and fine."""
    lr = members[k]
    itself = True
    for m in range(k):
        s, ta, tb = pair(m, k)
        if ta is None or tb is None:
            return
        if _norm_text(members[m].line.text) == _norm_text(lr.line.text):
            return
        same = ta.spelling == tb.spelling and (ta.vowel, ta.rest) == (tb.vowel, tb.rest)
        if not same and not one_word(members[m], lr):
            return
        itself = itself and same
    if k == 0:
        return
    first, word = pair(0, k)[1:]
    if word is None or first is None:
        return
    if itself:
        message = f"rhymes {_quote(word.word)} with itself"
    else:
        message = f"rhymes {_quote(word.word)} with {_quote(first.word)}, a form of the same word"
    lr.issues.append(
        Issue(
            lr.line.number,
            "rhyme",
            "warning",
            message,
            REFRAIN,
            {"word": word.word},
        )
    )


def rhyme_head(lr: LineReport) -> tuple | None:
    """A line's rhyme word as one_word compares it: its language, its syllables up
    to and with the stressed one, and the word."""
    w = rhyme.anchor_word(lr.line, lr.fit)
    if w is None:
        return None
    word, stress = lr.line.words[w], lr.fit.stresses.get(w)
    if stress is None:
        return None
    sung = tuple(s.text.lower().replace("ё", "е") for s in word.syllables)
    return word.lang, sung[: stress + 1], word.norm


def one_word(a: LineReport, b: LineReport) -> bool:
    """Whether two lines end on forms of one word: the same syllables up to and with
    the stressed one (сер-дце, сер-дца), not merely the same sound (луг, лук)."""
    return forms_of_one_word(rhyme_head(a), rhyme_head(b))


def forms_of_one_word(a: tuple | None, b: tuple | None) -> bool:
    """one_word for two rhyme_heads found already."""
    return a is not None and b is not None and a[:2] == b[:2] and a[2] != b[2]


def _norm_text(text: str) -> str:
    return " ".join(lyrics.tokenize(text.lower()))


def rhyming_set(members: list[LineReport]):
    """The members that hold a rhyme group together, and pair(i, j): rhyme.match
    of members i and j, tails in that order."""
    n = len(members)
    scores = {
        (i, j): rhyme.match(members[i].tails, members[j].tails)
        for i in range(n)
        for j in range(i + 1, n)
    }

    def pair(i: int, j: int):
        if i < j:
            return scores[i, j]
        s, a, b = scores[j, i]
        return s, b, a

    need = [rhyme.THRESHOLD[lr.min_rhyme] for lr in members]
    root = list(range(n))
    for (i, j), (s, _, _) in scores.items():
        if s >= need[j]:
            root[_find(root, j)] = _find(root, i)
    sizes = Counter(_find(root, k) for k in range(n))
    # on a tie, the set whose lines pass their own slots stands: a partner that
    # also misses its ending is the one to blame (расставаться, not рук)
    sound = Counter(_find(root, k) for k in range(n) if not _own_errors(members[k]))
    main = max(sizes, key=lambda r: (sizes[r], sound[r], r == _find(root, 0)))
    return {k for k in range(n) if _find(root, k) == main}, pair


def _own_errors(lr: LineReport) -> bool:
    return any(i.severity == "error" and i.code not in ("rhyme", "scheme") for i in lr.issues)


def _find(root: list[int], k: int) -> int:
    while root[k] != k:
        root[k] = root[root[k]]
        k = root[k]
    return k
