"""An MCP server over stdio, so an agent can check its own lyrics.

    ashugh mcp

speaks JSON-RPC 2.0, one message per line, and offers these tools:

* scan         check lyrics against a spec (TOML text); the full report
* syllables    how lines are sung: syllables, stress grid
* rhyme        the rhyme level of two words or lines
* requests     what each failing line must be, for the agent to write candidates
* pick         choose among candidate lines the agent wrote so the song passes
* translate    a song into another language on the same grid: requests, then picks
* suno         rewrite lyrics for Suno
* derive_spec  the spec that reproduces a song's form (for translations)
* spec_template a starter spec

Tool failures (a bad spec, a missing argument) come back as results with
isError set, so the agent can read them and retry; only protocol errors are
JSON-RPC errors.

Register it with Claude Code: claude mcp add ashugh -- ashugh mcp
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable

from . import __version__, meter, report, rhyme
from .fit import fit_song, requests_for
from .lang import ANALYZERS
from .lyrics import has_digits
from .proposers import ProposerError, StaticProposer, parse_candidates
from .scan import analyze_lines, scan
from .spec import Spec, SpecError, dumps, loads, template
from .suno import format_song
from .translate import derive_spec, parse_keep, source_warnings, translate_song

VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")


class ToolError(ValueError):
    pass


def _opt(args: dict, key: str) -> str | None:
    value = args.get(key)
    if value is not None and not isinstance(value, str):
        raise ToolError(f"{key} must be a string")
    return value


def _lang(args: dict) -> str | None:
    lang = _opt(args, "lang")
    if lang and lang not in ANALYZERS:
        raise ToolError(f"lang must be one of {', '.join(sorted(ANALYZERS))}, not {lang!r}")
    return lang


def _str(args: dict, key: str) -> str:
    value = _opt(args, key)
    if value is None:
        raise ToolError(f"missing argument: {key}")
    return value


def _spec(args: dict) -> Spec:
    text = _opt(args, "spec")
    spec = loads(text, "spec") if text else Spec()
    lang = _lang(args)
    if lang:
        spec.language = lang
    return spec


def t_scan(args: dict) -> dict:
    return report.as_dict(scan(_str(args, "lyrics"), _spec(args)))


def t_syllables(args: dict) -> dict:
    lines = []
    for ln in analyze_lines(_str(args, "text"), _spec(args), _lang(args)):
        f = meter.fit(ln.words, meter.parse_meter(_opt(args, "meter") or "free")[0])
        sung = " ".join(
            w.sung(f.stresses.get(i), mark=True, dropped=i in f.elided)
            for i, w in enumerate(ln.words)
        )
        ambiguous = [w.text for w in ln.words if w.ambiguous and w.size > 1]
        fewest, most = meter.syllable_range(ln.words, f)
        warnings = ["digits are not counted; spell numbers out"] if has_digits(ln.text) else []
        guessed = [w.text for w in ln.words if w.guessed]
        if guessed:
            warnings.append(f"not in the dictionaries, guessed: {', '.join(guessed)}")
        lines.append(
            {
                "text": ln.text,
                "syllables": f.count,
                "fewest": fewest,  # a line counts anywhere from fewest to most
                "most": most,
                "grid": f.grid,
                "sung": sung,
                "ambiguous": ambiguous,
                "warnings": warnings,
            }
        )
    return {"lines": lines}


def t_rhyme(args: dict) -> dict:
    a, b = _str(args, "a"), _str(args, "b")
    lang = _lang(args)
    lines = analyze_lines(f"{a}\n{b}", Spec(language=lang), lang)
    if len(lines) != 2:
        raise ToolError("a and b must each be a word or a line")
    s, x, y = rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))
    return {"level": rhyme.level(s), "score": s, "sounds": [t.sound if t else None for t in (x, y)]}


def t_pick(args: dict) -> dict:
    raw = args.get("candidates")
    if raw is None:
        raise ToolError("missing argument: candidates")
    try:
        candidates = parse_candidates(raw)
    except ProposerError as e:
        raise ToolError(str(e)) from None
    proposer = StaticProposer(candidates)
    result = fit_song(_str(args, "lyrics"), _spec(args), proposer, rounds=1)
    data = result.as_dict()
    data["ignored"] = proposer.unused({lr.line.number for lr in result.report.lines})
    return data


def t_requests(args: dict) -> dict:
    n = args.get("n", 6)
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:  # true is no count
        raise ToolError("n must be a whole number of 1 or more")
    warnings: list[str] = []
    reqs = requests_for(_str(args, "lyrics"), _spec(args), n, _lang(args), warnings)
    return {"requests": [r.as_dict() for r in reqs], "warnings": warnings}


class _Recorder:
    """A proposer that writes nothing: it keeps the requests it is sent."""

    name = "requests"

    def __init__(self) -> None:
        self.requests: list = []

    def propose(self, requests: list) -> dict:
        self.requests += requests
        return {}


def t_translate(args: dict) -> dict:
    target = _str(args, "to")
    if target not in ANALYZERS:
        raise ToolError(f"to must be one of {', '.join(sorted(ANALYZERS))}, not {target!r}")
    lyrics, source_lang = _str(args, "lyrics"), _lang(args)
    tolerance = args.get("tolerance", 0)
    if isinstance(tolerance, bool) or not isinstance(tolerance, int) or tolerance < 0:
        raise ToolError("tolerance must be a whole number of syllables, 0 or more")
    keep, min_rhyme = parse_keep(_opt(args, "keep")), _opt(args, "min_rhyme") or "near"
    if min_rhyme not in rhyme.THRESHOLD:
        levels = ", ".join(rhyme.THRESHOLD)
        raise ToolError(f"min_rhyme must be one of {levels}, not {min_rhyme!r}")

    def run(proposer):
        return translate_song(
            lyrics, target, proposer, keep, 1, source_lang=source_lang,
            tolerance=tolerance, min_rhyme=min_rhyme,
        )  # fmt: skip

    raw = args.get("candidates")
    if raw is None:  # the first step: what each line must be
        recorder = _Recorder()
        run(recorder)
        return {"requests": [r.as_dict() for r in recorder.requests]}
    try:
        candidates = parse_candidates(raw)
    except ProposerError as e:
        raise ToolError(str(e)) from None
    proposer = StaticProposer(candidates)
    result = run(proposer)
    data = result.as_dict()
    data["ignored"] = proposer.unused({lr.line.number for lr in result.report.lines})
    return data


def t_suno(args: dict) -> dict:
    tags = args.get("tags")
    if tags is None:
        tags = True
    if not isinstance(tags, bool):  # "false" is no boolean, and bool("false") is True
        raise ToolError("tags must be true or false")
    policy = args.get("policy")
    if policy is not None and not isinstance(policy, dict):
        raise ToolError("policy must be an object, as probe score writes it")
    try:
        result = format_song(
            _str(args, "lyrics"),
            _spec(args),
            stress=_opt(args, "stress") or "caps",
            armenian=_opt(args, "armenian") or "script",
            split=_opt(args, "split") or "none",
            schwa=_opt(args, "schwa") or "ə",
            tags=tags,
            policy=policy,
        )
    except ValueError as e:
        raise ToolError(str(e)) from None
    return {"text": result.text, "notes": [vars(n) for n in result.notes]}


def t_derive_spec(args: dict) -> dict:
    keep = parse_keep(_opt(args, "keep"))
    source_lang = _opt(args, "source_lang")
    if source_lang and source_lang not in ANALYZERS:
        raise ToolError(f"source_lang must be one of {', '.join(sorted(ANALYZERS))}")
    source = scan(_str(args, "lyrics"), lang=source_lang)
    notes: list[str] = []
    data = derive_spec(source, keep, notes)
    lang = _lang(args)
    if lang:
        data = {"language": lang, **data}
    return {"toml": dumps(data), "warnings": source_warnings(source) + notes}


def t_spec_template(args: dict) -> dict:
    return {"toml": template(_lang(args) or "hy")}


def _schema(required: list[str], **props: str) -> dict:
    kinds = {
        "candidates": {"type": ["object", "array"]},
        "tags": {"type": "boolean"},
        "lang": {"type": "string", "enum": ["hy", "ru", "en"]},
        "stress": {"type": "string", "enum": ["caps", "acute", "none"]},
        "armenian": {"type": "string", "enum": ["script", "schwa", "latin"]},
        "split": {"type": "string", "enum": ["none", "last", "all"]},
        "source_lang": {"type": "string", "enum": ["hy", "ru", "en"]},
        "tolerance": {"type": "integer", "minimum": 0},
        "min_rhyme": {"type": "string", "enum": ["perfect", "near", "slant", "assonance"]},
        "policy": {"type": "object"},
        "n": {"type": "integer", "minimum": 1},
    }
    return {
        "type": "object",
        "properties": {
            k: {**kinds.get(k, {"type": "string"}), "description": v} for k, v in props.items()
        },
        "required": required,
    }


SPEC_DOC = "song spec as TOML text (optional): syllables, meter, rhyme, sections, lexicon"
LANG_DOC = "hy, ru or en; detected when omitted"

TOOLS: dict[str, tuple[str, dict, Callable[[dict], dict]]] = {
    "scan": (
        "Check song lyrics against a spec: sung syllable counts (with Armenian hidden "
        "schwas), stress and meter, rhyme by sound, endings. Returns every line with "
        "its grid and every issue. Run it on any lyrics before presenting them.",
        _schema(
            ["lyrics"], lyrics="the lyrics, Suno-style [tags] allowed", spec=SPEC_DOC, lang=LANG_DOC
        ),
        t_scan,
    ),
    "syllables": (
        "Show how words or lines are sung: syllables split by hyphens with hidden vowels "
        "written out, stress marked, and the stress grid.",
        _schema(
            ["text"],
            text="words or lines",
            lang=LANG_DOC,
            meter="resolve stress against this meter",
            spec="song spec as TOML text (optional): its [lexicon] corrects words",
        ),
        t_syllables,
    ),
    "rhyme": (
        "Score how well two words or lines rhyme by sound: perfect, near, slant, "
        "assonance or none.",
        _schema(["a", "b"], a="first word or line", b="second word or line", lang=LANG_DOC),
        t_rhyme,
    ),
    "pick": (
        "Choose among candidate lines you wrote for the failing lines of a song so that "
        "every line fits its slot and rhyme groups hold. candidates maps line numbers "
        'to lists of alternatives: {"3": ["...", "..."]}. Returns the repaired lyrics, '
        "the changes and anything still unresolved.",
        _schema(
            ["lyrics", "candidates"],
            lyrics="the lyrics",
            spec=SPEC_DOC,
            candidates="line number -> candidate lines",
            lang=LANG_DOC,
        ),
        t_pick,
    ),
    "requests": (
        "What each failing line of a song must be, before you write candidates: its "
        "syllables, meter template, ending, the words it must rhyme with, its problems "
        "and the lines around it. A chorus written twice is asked once (see copies). "
        "Write candidates for each request, then call pick.",
        _schema(["lyrics"], lyrics="the lyrics", spec=SPEC_DOC, lang=LANG_DOC),
        t_requests,
    ),
    "translate": (
        "Translate a song into another language on the same syllable grid and rhymes. "
        "Call it first without candidates: it returns a request per line (the source "
        "line and the slot it must fill). Then call it again with candidates, line "
        "number -> translations, to get the song that fits.",
        _schema(
            ["lyrics", "to"],
            lyrics="the source lyrics",
            to="the target language: hy, ru or en",
            candidates="line number -> candidate translations (omit to get requests)",
            lang="the source language, detected when omitted",
            keep="comma-separated: syllables,meter,rhyme,endings (default syllables,rhyme); "
            "keep all four to sing the translation to the same melody",
            tolerance="syllables a line may be off its slot (default 0)",
            min_rhyme="perfect, near (default), slant or assonance",
        ),
        t_translate,
    ),
    "suno": (
        "Rewrite lyrics for Suno: restore ё, mark ambiguous Russian stress, spell out or "
        "romanize Armenian, hyphenate held notes, normalize section tags.",
        _schema(
            ["lyrics"],
            lyrics="the lyrics",
            spec=SPEC_DOC,
            stress="caps (default), acute or none",
            armenian="script (default), schwa or latin",
            split="none (default), last or all",
            schwa="the letter for a sung Armenian schwa in latin mode (default ə)",
            policy="what probe score learned Suno reads best, per language and word",
            tags="normalize and infer section tags (default true)",
            lang=LANG_DOC,
        ),
        t_suno,
    ),
    "derive_spec": (
        "The spec (TOML) that reproduces a song's form per stanza: syllable counts, meter, "
        "rhyme scheme, endings. Use it to translate a song into the same grid.",
        _schema(
            ["lyrics"],
            lyrics="the source song",
            keep="comma-separated: syllables,meter,rhyme,endings (default syllables,rhyme)",
            lang="language of the target spec",
            source_lang="language of the source song, detected per line when omitted",
        ),
        t_derive_spec,
    ),
    "spec_template": (
        "A starter spec to edit.",
        _schema([], lang="hy, ru or en"),
        t_spec_template,
    ),
}


class Server:
    def handle_batch(self, msg) -> dict | list | None:
        """A message or a batch of them: each answered, the notifications not."""
        if not isinstance(msg, list):
            return self.handle(msg)
        if not msg:
            return _error(None, -32600, "empty batch")
        replies = [r for r in (self.handle(m) for m in msg) if r is not None]
        return replies or None

    def handle(self, msg) -> dict | None:
        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or "method" not in msg:
            mid = msg.get("id") if isinstance(msg, dict) else None
            return _error(mid if _valid_id(mid) else None, -32600, "invalid request")
        method, params = msg["method"], msg.get("params")
        if "id" in msg and not _valid_id(msg["id"]):  # null, NaN, a list: no id at all
            return _error(None, -32600, "id must be a string or an integer")
        mid = msg.get("id")
        if not isinstance(method, str):
            return _error(mid, -32600, "method must be a string")
        if params is None:
            params = {}
        if mid is None:  # a notification: nothing to answer
            return None
        if not isinstance(params, dict):
            return _error(mid, -32602, "params must be an object")
        if method == "initialize":
            asked = params.get("protocolVersion")
            return _result(
                mid,
                {
                    "protocolVersion": asked if asked in VERSIONS else VERSIONS[0],
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "ashugh", "version": __version__},
                },
            )
        if method == "ping":
            return _result(mid, {})
        if method == "tools/list":
            tools = [
                {"name": name, "description": desc, "inputSchema": schema}
                for name, (desc, schema, _) in TOOLS.items()
            ]
            return _result(mid, {"tools": tools})
        if method == "tools/call":
            name = params.get("name")
            if not isinstance(name, str) or name not in TOOLS:
                return _error(mid, -32602, f"unknown tool: {name}")
            args = params.get("arguments")
            if args is None:
                args = {}
            if not isinstance(args, dict):  # [] and 0 too, not read as "no arguments"
                return _error(mid, -32602, "arguments must be an object")
            try:
                data, failed = TOOLS[name][2](args), False
            except (ToolError, SpecError, ProposerError, ValueError, OSError) as e:
                data, failed = {"error": str(e)}, True
            except Exception as e:  # a bug in one call must not take the server down
                data, failed = {"error": f"internal error: {type(e).__name__}: {e}"}, True
            text = json.dumps(data, ensure_ascii=False)
            return _result(mid, {"content": [{"type": "text", "text": text}], "isError": failed})
        return _error(mid, -32601, f"method not found: {method}")


def _valid_id(mid) -> bool:
    return (isinstance(mid, str) or isinstance(mid, int)) and not isinstance(mid, bool)


def _result(mid, result) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _error(mid, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def serve(stdin=None, stdout=None) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    server = Server()
    for line in stdin:
        if not line.strip():
            continue
        try:
            msg = json.loads(line.lstrip("\ufeff"))  # a BOM some clients send first
        except ValueError, RecursionError:  # [[[[... a hundred thousand deep, or 5,000 digits
            reply = _error(None, -32700, "parse error")
        else:
            try:
                reply = server.handle_batch(msg)
            except Exception as e:  # nothing a client sends may take the server down
                mid = msg.get("id") if isinstance(msg, dict) else None
                reply = _error(mid if _valid_id(mid) else None, -32603, f"internal error: {e}")
        if reply is not None:
            # ASCII on the wire: a lone surrogate (an emoji cut in half) stays escaped
            stdout.write(json.dumps(reply) + "\n")
            stdout.flush()
    return 0
