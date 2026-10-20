"""Command line: ashugh scan | syl | rhyme | spec."""

from __future__ import annotations

import argparse
import sys

from . import __version__, meter, report, rhyme
from . import lang as languages
from .scan import analyze_lines, scan
from .spec import Spec, SpecError, apply, load, template


def _read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _inline_rule(args: argparse.Namespace) -> dict:
    table: dict = {}
    if args.syllables:
        table["syllables"] = args.syllables
    if args.meter:
        table["meter"] = args.meter
    if args.feet:
        table["feet"] = args.feet
    if args.rhyme:
        table["rhyme"] = args.rhyme
    if args.endings:
        table["endings"] = args.endings
    if args.tolerance is not None:
        table["tolerance"] = args.tolerance
    if args.min_rhyme:
        table["min_rhyme"] = args.min_rhyme
    if args.forbid_final:
        table["forbid_final"] = args.forbid_final
    return table


def _spec(args: argparse.Namespace) -> Spec:
    spec = load(args.spec) if args.spec else Spec()
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
    print(template(args.lang or "hy"), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ashugh",
        description="Prosody checks for song lyrics in Armenian and Russian: "
        "syllables, stress, meter, rhyme.",
    )
    p.add_argument("--version", action="version", version=f"ashugh {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("scan", help="check a lyrics file against a spec (exit 1 on errors)")
    s.add_argument("file", help="lyrics file, or - for stdin")
    s.add_argument("--spec", help="song spec (TOML)")
    s.add_argument("--lang", choices=sorted(languages.ANALYZERS), help="force the language")
    s.add_argument("--json", action="store_true", help="machine-readable output")
    s.add_argument("-a", "--all", action="store_true", help="show every line, not only problems")
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
    s.set_defaults(func=cmd_scan)

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

    t = sub.add_parser("spec", help="print a starter spec")
    t.add_argument("--lang", choices=sorted(languages.ANALYZERS))
    t.set_defaults(func=cmd_spec)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        return args.func(args)
    except SpecError as e:
        print(f"ashugh: {e}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as e:
        print(f"ashugh: {e}", file=sys.stderr)
        return 2
