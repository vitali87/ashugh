"""Command line: ashugh scan | fit | pick | translate | suno | probe | syl | rhyme | spec |
mcp | lsp."""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

from . import __version__, lyrics, meter, probe, report, rhyme
from . import lang as languages
from .fit import FitResult, fit_song
from .proposers import DEFAULT_MODEL, ProposerError, StaticProposer, load_candidates, make_proposer
from .scan import analyze_lines, scan
from .spec import Spec, SpecError, apply, dumps, load, template
from .suno import format_song, load_policy
from .translate import derive_spec, parse_keep, translate_song


def _positive(value: str) -> int:
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError(f"must be 1 or more, got {value}")
    return n


def _read(path: str) -> str:
    """The file as saved: its line endings kept, a BOM dropped."""
    if path == "-":
        raw = getattr(sys.stdin, "buffer", None)
        return raw.read().decode("utf-8-sig") if raw else sys.stdin.read()
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return fh.read()


def _print_text(text: str) -> None:
    """Lyrics to stdout with their own line endings, untranslated."""
    if not text.endswith(("\n", "\r")):
        text += "\n"
    raw = getattr(sys.stdout, "buffer", None)
    if raw is None:
        sys.stdout.write(text)
        return
    sys.stdout.flush()
    raw.write(text.encode("utf-8"))
    raw.flush()


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
    if inline:  # flags override the spec's top level, every section and stanza
        spec.base = apply(inline, spec.base, "flags")
        spec.sections = {k: apply(inline, r, "flags") for k, r in spec.sections.items()}
        spec.stanzas = {k: apply(inline, r, "flags") for k, r in spec.stanzas.items()}
        spec.flags = inline
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


def cmd_requests(args: argparse.Namespace) -> int:
    from .fit import requests_for
    from .proposers import SCHEMA, SYSTEM

    reqs = requests_for(_read(args.file), _spec(args), n=args.n, lang=args.lang)
    data = {
        "system": SYSTEM,
        "answer_format": SCHEMA,
        "requests": [r.as_dict() for r in reqs],
    }
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def cmd_pick(args: argparse.Namespace) -> int:
    spec = _spec(args)
    proposer = StaticProposer(load_candidates(args.candidates))
    result = fit_song(
        _read(args.file), spec, proposer, rounds=1, solver=args.solver, lang=args.lang
    )
    ignored = proposer.unused({lr.line.number for lr in result.report.lines})
    if not args.json:
        for why in ignored:
            print(f"warning: {why}", file=sys.stderr)
    return _emit_fit(result, args, ignored)


def _emit_fit(result: FitResult, args: argparse.Namespace, ignored: list[str] | None = None) -> int:
    result.report.path = args.file
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="") as fh:
            fh.write(result.text)
    if args.json:
        data = result.as_dict()
        if ignored is not None:
            data["ignored"] = ignored  # candidates no request named
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0 if result.ok else 1
    log = sys.stderr if not args.output else sys.stdout
    written = lyrics.split_lines(result.text)
    for c in result.changes:  # the line as written, its backing vocal and stop in place
        shown = written[c.line - 1].strip() if c.line <= len(written) else c.new
        print(f"L{c.line}  {c.old}\n   → {shown}", file=log)
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
        _print_text(result.text)
    return 0 if result.ok else 1


def cmd_syl(args: argparse.Namespace) -> int:
    text = " ".join(args.text) if args.text else sys.stdin.read()
    spec = load(args.spec) if args.spec else Spec()
    if lyrics.has_digits(text):
        print("warning: digits are not counted; spell numbers out", file=sys.stderr)
    for ln in analyze_lines(text, spec, args.lang):
        f = meter.fit(ln.words, meter.parse_meter(args.meter or "free")[0])
        parts = []
        for i, w in enumerate(ln.words):
            st = f.stresses.get(i)
            sung = w.sung(st, mark=True, dropped=i in f.elided)
            note = ""
            if w.guessed and w.size > 1:
                note = "?"
            elif w.ambiguous:
                options = "/".join(w.sung(o, mark=True) for o in w.stress_options())
                note = f"({options})"
            parts.append(sung + note)
        fewest = f.count - max(len(r) for r in meter.realizations(ln.words)) + len(f.elided)
        count = f"{fewest}-{f.count}" if fewest < f.count else str(f.count)  # նա ստացավ: 3-4
        print(f"{count:>2}  {f.grid:14}  {' '.join(parts)}")
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


def cmd_suno(args: argparse.Namespace) -> int:
    result = format_song(
        _read(args.file),
        _spec(args),
        stress=args.stress,
        armenian=args.armenian,
        split=args.split,
        schwa=args.schwa,
        tags=not args.no_tags,
        policy=load_policy(args.policy) if args.policy else None,
        lang=args.lang,
    )
    if args.json:
        notes = [vars(n) for n in result.notes]
        print(json.dumps({"text": result.text, "notes": notes}, ensure_ascii=False, indent=2))
    else:
        _print_text(result.text)
    return 0


def cmd_probe_make(args: argparse.Namespace) -> int:
    plan = probe.make_probes(args.words, args.lang, args.modes.split(",") if args.modes else None)
    probe.save_plan(plan, args.output)
    if args.lyrics:
        folder = Path(args.lyrics)
        folder.mkdir(parents=True, exist_ok=True)
        for p in plan:
            (folder / f"{p.id}.txt").write_text(p.lyrics, encoding="utf-8")
    print(
        f"{len(plan)} probes -> {args.output}"
        + (f", lyrics in {args.lyrics}" if args.lyrics else "")
    )
    print("Generate each in Suno, save the clips as <probe id>.mp3, then run probe transcribe.")
    return 0


def cmd_probe_transcribe(args: argparse.Namespace) -> int:
    plan = probe.load_plan(args.plan)
    transcripts = probe.transcribe(args.clips, plan, model=args.model, engine=args.engine)
    Path(args.output).write_text(
        json.dumps(transcripts, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"{len(transcripts)}/{len(plan)} clips transcribed -> {args.output}")
    return 0 if transcripts else 1


def cmd_probe_score(args: argparse.Namespace) -> int:
    result = probe.score(probe.load_plan(args.plan), probe.load_transcripts(args.transcripts))
    for word, modes in result.scores.items():
        cells = "  ".join(f"{m} {s:.2f}" for m, s in modes.items())
        print(f"{word:20} {cells}")
    for lang, entry in result.policy.items():
        print(f"{lang}: default {entry['default']}, overrides {entry['words'] or 'none'}")
    if result.missing:
        print(f"no transcript for {len(result.missing)} probe(s): {', '.join(result.missing)}")
    data = {**result.policy, "scores": result.scores, "missing": result.missing}
    if args.output:
        Path(args.output).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return 0


def cmd_mcp(args: argparse.Namespace) -> int:
    from .mcp import serve

    return serve()


def cmd_lsp(args: argparse.Namespace) -> int:
    from .lsp import serve

    return serve()


def cmd_eval_run(args: argparse.Namespace) -> int:
    from . import evaluate

    tasks = evaluate.load_tasks(args.tasks)
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    writer = evaluate.make_writer(args.writer, args.model, args.effort)
    proposer = make_proposer(args.proposer, args.model, args.effort) if "ashugh" in modes else None
    rows = evaluate.run(tasks, writer, modes, proposer, rounds=args.rounds)
    summary = evaluate.summarize(rows)
    print(evaluate.table(summary))
    if args.output:
        Path(args.output).write_text(
            json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return 0


def cmd_eval_requests(args: argparse.Namespace) -> int:
    from . import evaluate

    data = evaluate.export_requests(evaluate.load_tasks(args.tasks), args.drafts, n=args.n)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"{sum(len(v['requests']) for v in data.values())} requests in {len(data)} songs")
    else:
        print(text)
    return 0


def cmd_eval_apply(args: argparse.Namespace) -> int:
    from . import evaluate

    try:
        candidates = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"{args.candidates}: {e}") from None
    if not isinstance(candidates, dict):
        raise ValueError(f"{args.candidates}: expected {{task id: {{line: [candidates]}}}}")
    rows = evaluate.apply_candidates(
        evaluate.load_tasks(args.tasks), args.drafts, candidates, args.out
    )
    changed = sum(r["changes"] for r in rows)
    print(f"{changed} line(s) changed in {len(rows)} songs -> {args.out}")
    return 0


def cmd_eval_report(args: argparse.Namespace) -> int:
    from . import evaluate

    try:
        data = json.loads(Path(args.results).read_text(encoding="utf-8"))
        rows = data["rows"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as e:
        raise ValueError(f"{args.results}: not an eval results file ({e})") from None
    needed = ("task", "language", "mode", "lines", "passing", "song_ok")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{args.results}: not an eval results file (no rows)")
    for k, row in enumerate(rows):
        if not isinstance(row, dict) or any(key not in row for key in needed):
            raise ValueError(
                f"{args.results}: not an eval results file (row {k} lacks {', '.join(needed)})"
            )
    print(evaluate.table(evaluate.summarize(rows)))
    for lang in sorted({r["language"] for r in rows}):
        print(f"\n{lang}")
        print(evaluate.table(evaluate.summarize([r for r in rows if r["language"] == lang])))
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
        description="Prosody checks for song lyrics in Armenian, Russian and English: "
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

    q = sub.add_parser("requests", help="the repair requests for a song's failing lines, as JSON")
    _song_args(q)
    q.add_argument("-n", type=_positive, default=6, help="candidates to ask for per line")
    q.set_defaults(func=cmd_requests)

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
    p.add_argument("--rounds", type=_positive, default=3, help="proposal rounds (default 3)")
    p.add_argument(
        "-n", type=_positive, default=6, help="candidates per line per round (default 6)"
    )


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

    su = sub.add_parser("suno", help="rewrite lyrics so Suno pronounces them as meant")
    _song_args(su)
    su.add_argument(
        "--stress",
        choices=["caps", "acute", "none"],
        default="caps",
        help="how to mark ambiguous Russian stress (default caps: зАмок)",
    )
    su.add_argument(
        "--armenian",
        choices=["script", "schwa", "latin"],
        default="script",
        help="Armenian as written, with hidden ը spelled out, or romanized",
    )
    su.add_argument("--schwa", default="ə", help="letter for the schwa in romanization")
    su.add_argument(
        "--split",
        choices=["none", "last", "all"],
        default="none",
        help="hyphenate sung syllables for held notes",
    )
    su.add_argument("--no-tags", action="store_true", help="leave section tags alone")
    su.add_argument("--policy", help="probe policy JSON choosing the Armenian mode per word")
    su.set_defaults(func=cmd_suno)

    sub.add_parser("mcp", help="run the MCP server on stdio").set_defaults(func=cmd_mcp)
    sub.add_parser("lsp", help="run the language server on stdio").set_defaults(func=cmd_lsp)

    ev = sub.add_parser("eval", help="measure spec pass rates: a writer alone vs with ashugh")
    evs = ev.add_subparsers(dest="eval", required=True)
    er = evs.add_parser("run", help="draft every task and score it")
    er.add_argument("tasks", help="a folder of task .toml files (see eval/tasks) or one file")
    er.add_argument("--writer", help="claude (default), cmd:<command> or dir:<drafts folder>")
    er.add_argument("--modes", default="alone,ashugh", help="alone,ashugh (default both)")
    er.add_argument("-o", "--output", help="write every row as JSON here")
    _proposer_args(er)
    er.set_defaults(func=cmd_eval_run)
    eq = evs.add_parser("requests", help="repair requests of failing drafts, for an outside agent")
    eq.add_argument("tasks")
    eq.add_argument("--drafts", required=True, help="folder of <task id>.txt drafts")
    eq.add_argument("-n", type=_positive, default=6)
    eq.add_argument("-o", "--output")
    eq.set_defaults(func=cmd_eval_requests)
    ea = evs.add_parser("apply", help="pick each draft against an agent's candidates")
    ea.add_argument("tasks")
    ea.add_argument("--drafts", required=True)
    ea.add_argument("--candidates", required=True, help='JSON {task id: {"3": ["..."]}}')
    ea.add_argument("--out", required=True, help="folder for the repaired drafts")
    ea.set_defaults(func=cmd_eval_apply)
    ep = evs.add_parser("report", help="summarize a results file, overall and per language")
    ep.add_argument("results")
    ep.set_defaults(func=cmd_eval_report)

    pr = sub.add_parser("probe", help="measure how Suno pronounces different spellings")
    prs = pr.add_subparsers(dest="probe", required=True)
    pm = prs.add_parser("make", help="write probe lyrics for words")
    pm.add_argument("words", nargs="+")
    pm.add_argument("--lang", required=True, choices=sorted(probe.MODES))
    pm.add_argument("--modes", help="comma-separated spellings to try (default all)")
    pm.add_argument("-o", "--output", default="probes.json", help="plan file (default probes.json)")
    pm.add_argument("--lyrics", help="also write one lyrics file per probe into this folder")
    pm.set_defaults(func=cmd_probe_make)
    pt = prs.add_parser("transcribe", help="transcribe clips with Whisper")
    pt.add_argument("clips", help="folder of <probe id>.mp3 (or .wav, .m4a ...) clips")
    pt.add_argument("--plan", default="probes.json")
    pt.add_argument("--model", default="small", help="Whisper model (default small)")
    pt.add_argument(
        "--engine",
        default="whisper",
        help='whisper (default), or cmd:"<command with {audio} and {lang}>" printing the text',
    )
    pt.add_argument("-o", "--output", default="transcripts.json")
    pt.set_defaults(func=cmd_probe_transcribe)
    ps = prs.add_parser("score", help="score transcripts and write a spelling policy")
    ps.add_argument("plan")
    ps.add_argument("transcripts", help="JSON {probe id: text} or a folder of <probe id>.txt")
    ps.add_argument("-o", "--output", help="write the policy here (for suno --policy)")
    ps.set_defaults(func=cmd_probe_score)

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
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        return args.func(args)
    except (SpecError, ProposerError, probe.ProbeError) as e:
        print(f"ashugh: {e}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as e:
        print(f"ashugh: {e}", file=sys.stderr)
        return 2
