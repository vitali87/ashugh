"""translate: singable translation that keeps the source's form.

The source song is scanned first. Per stanza, its syllable counts, meter and
feet, rhyme scheme and line endings become the target spec ([stanza.N]
tables), as far as --keep asks. Then every line becomes a variable with no
text of its own, the proposer translates it under its slot's constraints,
and the same check, solve and re-ask loop as fit picks the translation that
fits the grid and keeps the rhymes.
"""

from __future__ import annotations

from . import lyrics
from .fit import Change, FitResult, Unresolved, _variables, replace_lines, run
from .lang import ANALYZERS
from .proposers import Proposer
from .scan import Issue, Report, UnitReport, scan
from .spec import Spec, from_dict

KEEP = ("syllables", "meter", "rhyme", "endings")
DEFAULT_KEEP = frozenset({"syllables", "rhyme"})
ENDING_CODES = {0: "m", 1: "f", 2: "d"}


def parse_keep(text: str | None) -> set[str]:
    if not text:
        return set(DEFAULT_KEEP)
    keep = {k.strip() for k in text.split(",") if k.strip()}
    unknown = keep - set(KEEP)
    if unknown:
        raise ValueError(f"cannot keep {', '.join(sorted(unknown))}; choose from {', '.join(KEEP)}")
    return keep


def _scheme(letters: str) -> str | None:
    """A found scheme with lone letters freed and the rest relabeled: ABCB -> -A-A."""
    counts = {ch: letters.count(ch) for ch in letters if ch.isalpha()}
    relabel: dict[str, str] = {}
    out = []
    for ch in letters:
        if counts.get(ch, 0) < 2:
            out.append("-")
            continue
        if ch not in relabel:
            relabel[ch] = chr(ord("A") + len(relabel))
        out.append(relabel[ch])
    result = "".join(out)
    return result if any(c.isalpha() for c in result) else None


def derive_spec(report: Report, keep: set[str] | frozenset[str]) -> dict:
    """Per-stanza rules that reproduce the scanned song's form."""
    unknown = set(keep) - set(KEEP)
    if unknown:
        raise ValueError(f"cannot keep {', '.join(sorted(unknown))}; choose from {', '.join(KEEP)}")
    stanzas: dict[str, dict] = {}
    for number, unit in enumerate(report.units, 1):
        table: dict = {}
        if "syllables" in keep or "meter" in keep:
            table["syllables"] = [lr.fit.count for lr in unit.lines]
        # the stanza's meter only where every line keeps it: a spec its own song fails
        # would ask a translation for what the source never did
        kept = not any(lr.fit.off_beat or lr.fit.ending_off for lr in unit.lines)
        if "meter" in keep and unit.meter != "free" and kept:
            table["meter"] = unit.meter
            table["feet"] = [lr.fit.feet for lr in unit.lines]
        if "rhyme" in keep:
            scheme = _scheme(unit.scheme)
            if scheme:
                table["rhyme"] = scheme
        if "endings" in keep:  # a line of digits alone, counted 0, is left free
            table["endings"] = "".join(
                ENDING_CODES.get(lr.fit.ending, "h") if lr.fit.count else "-" for lr in unit.lines
            )
        stanzas[str(number)] = table
    return {"stanza": stanzas}


def source_warnings(report: Report) -> list[str]:
    """What makes a source line's slot unreliable: digits or words ashugh cannot count."""
    return [
        f"L{i.line}: {i.message} ({i.detail}); its slot counts only the words"
        for i in report.issues
        if i.code == "script"
    ]


def _faithful(original: str, text: str, faithfulness: float | None) -> float:
    del original, text
    return 0.3 + 0.6 * max(0.0, min(1.0, faithfulness)) if faithfulness is not None else 0.5


def translate_song(
    source: str,
    target: str,
    proposer: Proposer,
    keep: set[str] | frozenset[str] = DEFAULT_KEEP,
    rounds: int = 3,
    n: int = 6,
    solver: str = "auto",
    source_lang: str | None = None,
    tolerance: int = 0,
    min_rhyme: str = "near",
) -> FitResult:
    if target not in ANALYZERS:
        raise ValueError(f"cannot translate into {target!r}; use {', '.join(sorted(ANALYZERS))}")
    src = scan(source, Spec(), lang=source_lang)
    if not src.lines:
        raise ValueError("the source has no lyric lines to translate")
    data = derive_spec(src, keep)
    data.update(language=target, tolerance=tolerance, min_rhyme=min_rhyme)
    spec = from_dict(data)
    result = translate_with_spec(src, spec, proposer, rounds, n, solver)
    result.warnings = source_warnings(src)
    return result


def translate_with_spec(
    src: Report, spec: Spec, proposer: Proposer, rounds: int = 3, n: int = 6, solver: str = "auto"
) -> FitResult:
    target = spec.language
    units = []
    for u, unit in enumerate(src.units):
        rule = spec.rule_for(unit.key, u)
        # Without a meter to keep, a candidate's ambiguous words are read in the meter
        # the source stanza has, as the scan of the result will most likely read them
        # (мою́ in an iamb), not in free verse (мо́ю).
        meter_name = rule.meter or unit.meter
        source = "spec" if rule.meter else "detected"
        units.append(UnitReport(unit.section, unit.key, meter_name, source, "", rule, unit.lines))
    frame = Report(src.path, spec, units, src.text)
    variables, groups = _variables(frame, keep_original=False, everything=True)
    lines = {lr.line.number: lr for lr in frame.lines}

    def as_translation(var, req) -> None:
        req.source, req.source_lang = req.original, var.lr.line.lang
        req.original, req.lang = "", target
        req.problems = list(var.blocked)

    warnings: list[str] = []
    used, asked = run(
        variables,
        groups,
        lines,
        spec,
        proposer,
        rounds,
        n,
        solver,
        target,
        _faithful,
        as_translation,
        partners_from_lines=False,
        warnings=warnings,
    )
    new, changes, unresolved = {}, [], []
    for k in sorted(variables):
        var = variables[k]
        chosen = var.chosen
        if chosen is None:
            rejected = [{"text": t, "why": why} for t, why in var.rejected]
            unresolved.append(Unresolved(k, var.blocked or ["no candidate fit"], rejected))
            best = max(var.pool, key=lambda c: c.weight, default=None)
            text = best.text if best else _first_attempt(var.rejected)
        else:
            text = chosen.text
        if text:
            new[k] = text
            changes.append(
                Change(k, var.lr.line.text, text, round(chosen.weight, 3) if chosen else 0.0)
            )
    out = replace_lines(src.text, new, lang=target, asides=False)
    out = "".join(lyrics.retag(line) for line in lyrics.split_lines(out, keepends=True))
    report = scan(out, spec, lang=target)
    why = {u.line: u.reasons[0] for u in unresolved}
    for lr in report.lines:  # an attempt that failed its checks is no translation that passes
        k = lr.line.number
        if k in variables and k not in new:
            issue = Issue(k, "translate", "error", "not translated", "no candidate came back")
        elif k in why:
            issue = Issue(k, "translate", "error", "no translation fits", why[k])
        else:
            continue
        lr.issues.append(issue)
    return FitResult(out, report, changes, unresolved, used, asked, warnings)


def _first_attempt(rejected: list[tuple[str, str]]) -> str | None:
    return rejected[0][0] if rejected else None
