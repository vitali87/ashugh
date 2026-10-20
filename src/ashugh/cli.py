"""Command line: ashugh scan | fit | pick | translate | syl | rhyme | spec."""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__, meter, report, rhyme
from . import lang as languages
from .fit import FitResult, fit_song
from .proposers import DEFAULT_MODEL, ProposerError, StaticProposer, load_candidates, make_proposer
from .scan import analyze_lines, scan
from .spec import Spec, SpecError, apply, dumps, load, template
from .translate import derive_spec, parse_keep, translate_song


def _read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _inline_rule(args: argparse.Namespace) -> dict:
    table: dict = {}
    for key in ("syllables", "meter", "feet", "rhyme", "endings", "min_rhyme", "forbid_final"):
        value = getattr(args, key, None)
        if value:
            table[key] = value
    if getattr(args, "tolerance", None) is not None:
        table["tolerance"] = args.tolerance
    return table


def _spec(args: argparse.Namespace) -> Spec:
    spec = load(args.spec) if getattr(args, "spec", None) else Spec()
    inline = _inline_rule(args)
    if inline:  # flags override the spec's top level and every section
        spec.base = apply(inline, spec.base, "flags")
        spec.sections = {k: apply(inline, r, "flags") for k, r in spec.sections.items()}
    return spec


def cmd_scan(args: argparse.Namespace) -> int:
    spec = _spec(args)
    rep = scan(_read(args.file), spec, path=args.file, lang=args.lang)
    print(report.as_json(rep) if args.json else report.text(rep, show_all=args.all))
    return 0 if rep.ok else 1


def cmd_fit(args: argparse.Namespace) -> int:
    spec = _spec(args)
    proposer = make_proposer(args.proposer, args.model, args.effort)
    result = fit_song(
        _read(args.file),
        spec,
        proposer,
        rounds=args.rounds,
        n=args.n,
        solver=args.solver,
        lang=args.lang,
    )
    return _emit_fit(result, args)


def cmd_pick(args: argparse.Namespace) -> int:
    spec = _spec(args)
    proposer = StaticProposer(load_candidates(args.candidates))
    result = fit_song(
        _read(args.file), spec, proposer, rounds=1, solver=args.solver, lang=args.lang
    )
    return _emit_fit(result, args)


def _emit_fit(result: FitResult, args: argparse.Namespace) -> int:
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(result.text)
    if args.json:
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
        return 0 if result.ok else 1
    log = sys.stderr if not args.output else sys.stdout
    for c in result.changes:
        print(f"L{c.line}  {c.old}\n   → {c.new}", file=log)
    for u in result.unresolved:
        print(f"L{u.line}  unresolved: {'; '.join(u.reasons)}", file=log)
    rep = result.report
    passing = sum(1 for lr in rep.lines if lr.ok)
    print(
        f"{len(result.changes)} line(s) changed in {result.rounds} round(s) · "
        f"{len(result.unresolved)} unresolved · {passing}/{len(rep.lines)} lines pass",
        file=log,
    )
    if not args.output:
        print(result.text, end="" if result.text.endswith("\n") else "\n")
    return 0 if result.ok else 1


def cmd_syl(args: argparse.Namespace) -> int:
    text = " ".join(args.text) if args.text else sys.stdin.read()
    spec = load(args.spec) if args.spec else Spec()
    for ln in analyze_lines(text, spec, args.lang):
        f = meter.fit(ln.words, args.meter or "free")
        parts = []
        for i, w in enumerate(ln.words):
            st = f.stresses.get(i)
            sung = w.sung(st, mark=True)
            note = ""
            if w.guessed and w.size > 1:
                note = "?"
            elif w.ambiguous:
                options = "/".join(w.sung(o, mark=True) for o in w.stress_options())
                note = f"({options})"
            parts.append(sung + note)
        print(f"{f.count:>2}  {f.grid:14}  {' '.join(parts)}")
    return 0


def cmd_rhyme(args: argparse.Namespace) -> int:
    spec = Spec(language=args.lang)
    lines = analyze_lines(f"{args.a}\n{args.b}", spec, args.lang)
    if len(lines) != 2:
        print("give two words or lines", file=sys.stderr)
        return 2
    s, a, b = rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))
    shown = " / ".join(t.sound if t else "?" for t in (a, b))
    print(f"{rhyme.level(s)} {s:.2f}  {shown}")
    return 0 if s >= rhyme.THRESHOLD["near"] else 1


def cmd_spec(args: argparse.Namespace) -> int:
    if not args.source:
        print(template(args.lang or "hy"), end="")
        return 0
    data = derive_spec(scan(_read(args.source), lang=args.source_lang), parse_keep(args.keep))
    if args.lang:
        data = {"language": args.lang, **data}
    print(dumps(data), end="")
    return 0


def cmd_translate(args: argparse.Namespace) -> int:
    proposer = make_proposer(args.proposer, args.model, args.effort)
    result = translate_song(
        _read(args.file),
        args.to,
        proposer,
        keep=parse_keep(args.keep),
        rounds=args.rounds,
        n=args.n,
        solver=args.solver,
        source_lang=args.source_lang,
        tolerance=args.tolerance or 0,
    )
    return _emit_fit(result, args)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ashugh",
        description="Prosody checks for song lyrics in Armenian and Russian: "
        "syllables, stress, meter, rhyme.",
    )
    p.add_argument("--version", action="version", version=f"ashugh {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("scan", help="check a lyrics file against a spec (exit 1 on errors)")
    _song_args(s)
    s.add_argument("-a", "--all", action="store_true", help="show every line, not only problems")
    s.set_defaults(func=cmd_scan)

    f = sub.add_parser("fit", help="repair failing lines with candidates from an LLM")
    _song_args(f)
    _proposer_args(f)
    _fit_args(f)
    f.set_defaults(func=cmd_fit)

    k = sub.add_parser("pick", help="choose among candidate lines you already have")
    _song_args(k)
    k.add_argument("--candidates", required=True, help='JSON: {"3": ["line", "line"], ...}')
    _fit_args(k)
    k.set_defaults(func=cmd_pick)

    _more_commands(sub)
    return p


def _song_args(s: argparse.ArgumentParser) -> None:
    s.add_argument("file", help="lyrics file, or - for stdin")
    s.add_argument("--spec", help="song spec (TOML)")
    s.add_argument("--lang", choices=sorted(languages.ANALYZERS), help="force the language")
    s.add_argument("--json", action="store_true", help="machine-readable output")
    g = s.add_argument_group("inline rules (override the spec everywhere)")
    g.add_argument("--syllables", help='syllables per line: 8 or "8,8,8,6"')
    g.add_argument(
        "--meter",
        help="iamb, trochee, dactyl, amphibrach, anapest, dolnik, free; "
        "a number of feet may follow (iamb4)",
    )
    g.add_argument("--feet", help='feet per line: 4 or "4,3"')
    g.add_argument("--rhyme", help="rhyme scheme, e.g. ABAB, AABB, AbAb, .A.A")
    g.add_argument("--endings", help="m/f/d per line, e.g. fmfm")
    g.add_argument("--tolerance", type=int, help="allowed miss in syllables")
    g.add_argument("--min-rhyme", choices=["perfect", "near", "slant", "assonance"])
    g.add_argument(
        "--forbid-final", action="append", help="a line may not end in this (repeatable)"
    )


def _proposer_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--proposer",
        help="claude (default), cmd:<command reading JSON requests>, or file:<candidates.json>",
    )
    p.add_argument("--model", help=f"Claude model (default {DEFAULT_MODEL})")
    p.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"])
    p.add_argument("--rounds", type=int, default=3, help="proposal rounds (default 3)")
    p.add_argument("-n", type=int, default=6, help="candidates per line per round (default 6)")


def _fit_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("-o", "--output", help="write the repaired lyrics here (default: stdout)")
    p.add_argument("--solver", choices=["auto", "exact", "cpsat"], default="auto")


def _more_commands(sub) -> None:
    y = sub.add_parser("syl", help="show how words or lines are sung: syllables and stress")
    y.add_argument("text", nargs="*", help="text (default: stdin)")
    y.add_argument("--lang", choices=sorted(languages.ANALYZERS))
    y.add_argument("--meter", help="resolve ambiguous stress against this meter")
    y.add_argument("--spec", help="use this spec's [lexicon]")
    y.set_defaults(func=cmd_syl)

    r = sub.add_parser("rhyme", help="score how well two words or lines rhyme")
    r.add_argument("a")
    r.add_argument("b")
    r.add_argument("--lang", choices=sorted(languages.ANALYZERS))
    r.set_defaults(func=cmd_rhyme)

    t = sub.add_parser("spec", help="print a starter spec, or the form of an existing song")
    t.add_argument("--lang", choices=sorted(languages.ANALYZERS), help="language of the spec")
    t.add_argument("--from", dest="source", help="derive the spec from this song's form")
    t.add_argument(
        "--keep", help="with --from: syllables,meter,rhyme,endings (default syllables,rhyme)"
    )
    t.add_argument("--source-lang", choices=sorted(languages.ANALYZERS))
    t.set_defaults(func=cmd_spec)

    tr = sub.add_parser("translate", help="translate a song into the same syllable grid and rhymes")
    tr.add_argument("file", help="source lyrics, or - for stdin")
    tr.add_argument("--to", required=True, choices=sorted(languages.ANALYZERS))
    tr.add_argument("--keep", help="syllables,meter,rhyme,endings (default syllables,rhyme)")
    tr.add_argument("--source-lang", choices=sorted(languages.ANALYZERS))
    tr.add_argument("--tolerance", type=int, help="allowed miss in syllables")
    tr.add_argument("--json", action="store_true", help="machine-readable output")
    _proposer_args(tr)
    _fit_args(tr)
    tr.set_defaults(func=cmd_translate)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        return args.func(args)
    except (SpecError, ProposerError) as e:
        print(f"ashugh: {e}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as e:
        print(f"ashugh: {e}", file=sys.stderr)
        return 2
