"""Where candidate lines come from.

A proposer takes Requests (one per line to write, with its constraints and
what went wrong before) and returns candidates per request id. The engine
checks every candidate itself, so a proposer only has to be fluent, not right.

* ClaudeProposer asks Claude through the Anthropic SDK (pip install
  'ashugh[claude]'), one batched call per round.
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
        if not isinstance(entry, dict) or entry.get("id") not in wanted:
            continue
        candidates = entry.get("candidates")
        if isinstance(candidates, list):
            out[entry["id"]].extend(candidates)
    return out


class StaticProposer:
    name = "file"

    def __init__(self, candidates: dict[int, list[str]]) -> None:
        self.candidates = candidates

    def propose(self, requests: list[Request]) -> dict[str, list]:
        return {r.id: list(self.candidates.get(r.line, [])) for r in requests}


def load_candidates(path: str | Path) -> dict[int, list[str]]:
    """{"3": ["...", "..."]} or [{"line": 3, "candidates": [...]}], keyed by line number."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ProposerError(f"{path}: {e}") from None
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
    out: dict[int, list[str]] = {}
    for key, cands in pairs:
        try:
            number = int(key)
        except (TypeError, ValueError):
            raise ProposerError(f"{path}: {key!r} is not a line number") from None
        if not isinstance(cands, list) or not all(isinstance(c, str) for c in cands):
            raise ProposerError(f"{path}: line {number} needs a list of strings")
        out.setdefault(number, []).extend(cands)
    return out


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
- template: "/" marks a syllable that must carry stress, "x" one that must not.
- rhyme_with: the line's last stressed vowel and everything after it must \
sound like these words' (by sound, not spelling).
- rejected: earlier candidates that failed, with the reason. Do not repeat them.

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
                    "the Claude proposer needs the Anthropic SDK: pip install 'ashugh[claude]'"
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


def _api_errors() -> tuple[type[BaseException], ...]:
    try:
        import anthropic
    except ImportError:
        return ()
    return (anthropic.APIError,)


def _describe_api_error(e: Exception) -> str:
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


def make_proposer(spec: str | None, model: str | None = None, effort: str | None = None):
    """claude | cmd:<command line> | file:<candidates.json>; default from $ASHUGH_PROPOSER."""
    spec = spec or os.environ.get("ASHUGH_PROPOSER") or "claude"
    if spec == "claude":
        return ClaudeProposer(model=model or DEFAULT_MODEL, effort=effort or "medium")
    if spec.startswith("cmd:"):
        return CommandProposer(shlex.split(spec[4:]))
    if spec.startswith("file:"):
        return StaticProposer(load_candidates(spec[5:]))
    raise ProposerError(f"unknown proposer {spec!r}; use claude, cmd:<command> or file:<path>")
