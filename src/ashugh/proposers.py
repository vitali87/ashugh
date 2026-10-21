"""Where candidate lines come from.

A proposer takes Requests (one per line to write, with its constraints and
what went wrong before) and returns candidates per request id. The engine
checks every candidate itself, so a proposer only has to be fluent, not right.

* ClaudeProposer asks Claude through the Anthropic SDK (the claude extra),
  one batched call per round.
* CommandProposer runs any program: the requests go to its stdin as JSON and
  it prints the candidates as JSON. This plugs in other models or scripts.
* StaticProposer serves candidates someone already wrote, e.g. an agent that
  drafted alternatives itself (ashugh pick --candidates file.json).

The JSON a proposer returns:

    {"lines": [{"id": "L3", "candidates": ["...", {"text": "...", "faithfulness": 0.8}]}]}
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol

from . import install_hint

DEFAULT_MODEL = "claude-opus-5-5"


class ProposerError(RuntimeError):
    pass


@dataclass
class Request:
    id: str
    line: int
    lang: str
    original: str
    section: str = ""
    before: list[str] = field(default_factory=list)
    after: list[str] = field(default_factory=list)
    syllables: int | None = None
    tolerance: int = 0
    meter: str | None = None
    feet: int | None = None
    template: str | None = None  # stress pattern to match, "/" stressed, "x" not
    ending: str | None = None  # masculine | feminine | dactylic
    rhyme_with: list[str] = field(default_factory=list)  # words the line must rhyme with
    rhyme_sound: str | None = None
    avoid_final: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)  # earlier candidates and why they failed
    copies: list[int] = field(default_factory=list)  # the same line again: one repair for all
    source: str | None = None  # translate: the line being translated
    source_lang: str | None = None
    n: int = 6

    def as_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v not in (None, [], "")}


class Proposer(Protocol):
    name: str

    def propose(self, requests: list[Request]) -> dict[str, list]: ...


def parse_lines(data, requests: list[Request]) -> dict[str, list]:
    """Candidates per request id from a proposer's JSON answer."""
    if not isinstance(data, dict) or not isinstance(data.get("lines"), list):
        raise ProposerError('the answer must be an object with a "lines" list')
    wanted = {r.id for r in requests}
    out: dict[str, list] = {r.id: [] for r in requests}
    for entry in data["lines"]:
        if not isinstance(entry, dict):
            continue
        key = _request_id(entry.get("id", entry.get("line")))
        if key not in wanted:
            continue
        candidates = entry.get("candidates")
        if isinstance(candidates, list):
            out[key].extend(candidates)
    return out


def _request_id(value) -> str | None:
    """A request id as a proposer may write it: "L5", "5" or 5 are all L5."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return f"L{value}"
    if isinstance(value, str):
        text = value.strip()
        number = text.isascii() and text.isdigit()
        return f"L{text}" if number else text.upper() if text[:1] in "lL" else text
    return None


class StaticProposer:
    name = "file"

    def __init__(self, candidates: dict[int, list]) -> None:
        self.candidates = candidates
        self.asked: set[int] = set()  # the lines a request named

    def propose(self, requests: list[Request]) -> dict[str, list]:
        self.asked |= {r.line for r in requests}
        return {r.id: list(self.candidates.get(r.line, [])) for r in requests}

    def unused(self, lyric_lines: set[int]) -> list[str]:
        """Why the candidates of lines no request named went unused."""
        out = []
        for line in sorted(set(self.candidates) - self.asked):
            if line not in lyric_lines:
                out.append(f"line {line} is no lyric line (lines count from the file's first)")
            else:
                out.append(f"line {line} already passes; its candidates were not needed")
        return out


def load_candidates(path: str | Path) -> dict[int, list]:
    """A candidates file in any form parse_candidates reads, keyed by line number."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ProposerError(f"{path}: {e}") from None
    return parse_candidates(data, str(path))


def parse_candidates(data, path: str = "candidates") -> dict[int, list]:
    """Candidates by line number from {"3": [...]}, {"L3": [...]}, [{"line": 3,
    "candidates": [...]}] or a proposer's answer, {"lines": [{"id": "L3", ...}]}.
    A candidate is a string or {"text": ..., "faithfulness": ...}."""
    if isinstance(data, dict) and isinstance(data.get("lines"), list):
        data = [
            {"line": e.get("line", e.get("id")), "candidates": e.get("candidates")}
            if isinstance(e, dict)
            else e
            for e in data["lines"]
        ]
    if isinstance(data, list):
        pairs = []
        for entry in data:
            if not isinstance(entry, dict) or "line" not in entry or "candidates" not in entry:
                raise ProposerError(f'{path}: list entries need "line" and "candidates"')
            pairs.append((entry["line"], entry["candidates"]))
    elif isinstance(data, dict):
        pairs = list(data.items())
    else:
        raise ProposerError(f"{path}: expected an object or a list")
    out: dict[int, list] = {}
    for key, cands in pairs:
        number = _line_number(key)
        if number is None:
            raise ProposerError(f"{path}: {key!r} is not a line number")
        if not isinstance(cands, list) or not all(_candidate(c) for c in cands):
            raise ProposerError(
                f'{path}: line {number} needs a list of lines or {{"text": ...}} objects'
            )
        out.setdefault(number, []).extend(cands)
    return out


def _line_number(key) -> int | None:
    """A line number as a candidates file may write it: 3, "3" or "L3"; not 2.9,
    true, "1_0" or "²", which int() would take."""
    if isinstance(key, int) and not isinstance(key, bool):
        return key if key >= 1 else None
    if isinstance(key, str):
        text = key.strip()
        text = text[1:] if text[:1] in "Ll" else text
        if text.isascii() and text.isdigit() and int(text) >= 1:
            return int(text)
    return None


def _candidate(c) -> bool:
    return isinstance(c, str) or (isinstance(c, dict) and isinstance(c.get("text"), str))


class CommandProposer:
    name = "command"

    def __init__(self, argv: list[str], timeout: float = 600.0) -> None:
        if not argv:
            raise ProposerError("the proposer command is empty")
        self.argv = argv
        self.timeout = timeout

    def propose(self, requests: list[Request]) -> dict[str, list]:
        payload = json.dumps({"requests": [r.as_dict() for r in requests]}, ensure_ascii=False)
        try:
            done = subprocess.run(
                self.argv,
                input=payload,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",  # a stray byte must not end the run
                timeout=self.timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            raise ProposerError(f"proposer command failed: {e}") from None
        if done.returncode != 0:
            raise ProposerError(
                f"proposer command exited {done.returncode}: {done.stderr.strip()[:300]}"
            )
        try:
            data = json.loads(done.stdout)
        except json.JSONDecodeError:
            raise ProposerError("proposer command did not print JSON") from None
        return parse_lines(data, requests)


SYSTEM = """\
You write alternative lines for song lyrics. Each request is one line of a song \
that breaks its slot: the wrong number of sung syllables, stress off the beat, \
a broken rhyme, or a forbidden ending. Propose candidates for it.

A separate checker measures every candidate by its phonology and keeps only the \
ones that fit, so propose several genuinely different options rather than \
one careful one. Stay in the song's language, keep the line's meaning and \
imagery, and keep the voice of the lines around it. Prefer natural word \
order over padding with filler words.

Counting rules the checker uses:
- Syllables are sung syllables. Armenian sings schwas it does not write: \
a word-initial ս, զ or շ before a stop adds one (սպասել is ըս-պա-սել, 3), and \
consonant clusters add ը between consonants (Մկրտիչ is մը-կըր-տիչ, 3; գրել is \
գը-րել, 2). Armenian stress is on the last full vowel. Russian stress is lexical; \
ё is always stressed.
- template: "/" marks a beat, where a stressed syllable belongs (a one-syllable \
word may also sit there unstressed); "x" marks an off-beat, where no word's own \
stress may fall.
- rhyme_with: the line's last stressed vowel and everything after it must \
sound like these words' (by sound, not spelling). rhyme_sound is that rime; \
with rhyme_with empty it is the line's own rhyme, to keep. Never end on the \
same word as a partner.
- rejected: earlier candidates that failed, with the reason. Do not repeat them.

A request with a "source" line is a translation: original is empty, and each \
candidate is a singable translation of source (from source_lang) into lang \
that fits the constraints. Sense and imagery matter more than word-for-word \
accuracy; faithfulness is then measured against the source line.

For each request return n candidates, the most faithful first, each with a \
faithfulness score from 0 to 1 for how much of the original meaning it keeps.\
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "candidates": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "faithfulness": {"type": "number"},
                            },
                            "required": ["text", "faithfulness"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["id", "candidates"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["lines"],
    "additionalProperties": False,
}


class ClaudeProposer:
    name = "claude"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        effort: str = "medium",
        client=None,
        max_tokens: int = 16000,
        system: str = SYSTEM,
    ) -> None:
        self.model = model
        self.effort = effort
        self._client = client
        self.max_tokens = max_tokens
        self.system = system

    @property
    def client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError:
                raise ProposerError(
                    f"the Claude proposer needs the Anthropic SDK: {install_hint('claude')}"
                ) from None
            self._client = anthropic.Anthropic()
        return self._client

    def request_body(self, requests: list[Request]) -> dict:
        payload = json.dumps({"requests": [r.as_dict() for r in requests]}, ensure_ascii=False)
        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": self.system,
            "messages": [{"role": "user", "content": payload}],
            "output_config": {
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": SCHEMA},
            },
            "betas": ["server-side-fallback-2026-07-01"],
            "fallbacks": "default",
        }

    def propose(self, requests: list[Request]) -> dict[str, list]:
        client = self.client
        try:
            response = client.beta.messages.create(**self.request_body(requests))
        except _api_errors() as e:
            raise ProposerError(_describe_api_error(e)) from None
        except TypeError as e:
            raise ProposerError(no_credentials(e, "--proposer cmd:<program>")) from None
        if response.stop_reason == "refusal":
            raise ProposerError("Claude declined to write these lines")
        if response.stop_reason == "max_tokens":
            raise ProposerError("Claude's answer was cut off; ask for fewer candidates (-n)")
        text = next((b.text for b in response.content if getattr(b, "type", "") == "text"), "")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            raise ProposerError("Claude did not return JSON") from None
        return parse_lines(data, requests)


def no_credentials(e: TypeError, instead: str) -> str:
    """The message for the SDK's 'no credentials' TypeError; any other one is raised."""
    if "authentication" not in str(e).lower():
        raise e
    return (
        "Claude needs credentials: set ANTHROPIC_API_KEY (or run `ant auth login`), "
        f"or use {instead} instead"
    )


def _api_errors() -> tuple[type[BaseException], ...]:
    try:
        import anthropic
    except ImportError:
        return ()
    return (anthropic.APIError,)


def _describe_api_error(e: BaseException) -> str:
    import anthropic

    if isinstance(e, anthropic.AuthenticationError):
        return "Claude rejected the credentials; set ANTHROPIC_API_KEY or run `ant auth login`"
    if isinstance(e, anthropic.NotFoundError):
        return f"unknown model or endpoint: {e}"
    if isinstance(e, anthropic.RateLimitError):
        return "Claude is rate limiting these requests; try again shortly"
    if isinstance(e, anthropic.APIStatusError):
        return f"Claude returned HTTP {e.status_code}: {e.message}"
    if isinstance(e, anthropic.APIConnectionError):
        return "could not reach the Claude API (network)"
    return f"Claude request failed: {e}"


def _command_timeout() -> float:
    raw = os.environ.get("ASHUGH_PROPOSER_TIMEOUT")
    if raw is None:
        return 600.0
    try:
        seconds = float(raw)
    except ValueError:
        seconds = float("nan")
    if not seconds > 0 or seconds == float("inf"):
        raise ProposerError(
            f"ASHUGH_PROPOSER_TIMEOUT must be a positive number of seconds: {raw!r}"
        )
    return seconds


def make_proposer(spec: str | None, model: str | None = None, effort: str | None = None):
    """claude | cmd:<command line> | file:<candidates.json>; default from $ASHUGH_PROPOSER."""
    spec = spec or os.environ.get("ASHUGH_PROPOSER") or "claude"
    if spec == "claude":
        return ClaudeProposer(model=model or DEFAULT_MODEL, effort=effort or "medium")
    if spec.startswith("cmd:"):
        return CommandProposer(shlex.split(spec[4:]), timeout=_command_timeout())
    if spec.startswith("file:"):
        return StaticProposer(load_candidates(spec[5:]))
    raise ProposerError(f"unknown proposer {spec!r}; use claude, cmd:<command> or file:<path>")
