"""eval: the share of lines that meet the spec, a writer alone versus with ashugh.

A task is a TOML file: an id, a language, a prompt, and a [spec] table.

    id = "hy-night-city"
    language = "hy"
    prompt = "A short song about waiting for someone at night in the city."

    [spec]
    syllables = 8
    rhyme = "ABAB"

For every task the writer drafts lyrics from the prompt and the spec (put
into words). Mode "alone" scores the draft as it is; mode "ashugh" repairs it
with fit first. The score is the share of lines without errors and whether
the whole song passes.

Writers: claude (the Anthropic SDK), cmd:<program> (the task as JSON on its
stdin, the lyrics on its stdout) or dir:<folder> (drafts already written,
<task id>.txt), which makes runs reproducible and lets drafts be reused.
"""

from __future__ import annotations

import json
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .fit import fit_song
from .lang import ANALYZERS, NAMES
from .proposers import DEFAULT_MODEL, Proposer, ProposerError, _api_errors, _describe_api_error
from .scan import Report, scan
from .spec import Rule, Spec, SpecError, from_dict

MODES = ("alone", "ashugh")


@dataclass
class Task:
    id: str
    language: str
    prompt: str
    spec: Spec
    path: str = ""


def load_tasks(path: str | Path) -> list[Task]:
    path = Path(path)
    files = sorted(path.glob("*.toml")) if path.is_dir() else [path]
    tasks, seen = [], set()
    for file in files:
        try:
            data = tomllib.loads(file.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as e:
            raise ValueError(f"{file}: {e}") from None
        tid, lang, prompt = data.get("id"), data.get("language"), data.get("prompt")
        if not isinstance(tid, str) or not tid:
            raise ValueError(f"{file}: a task needs an id")
        if lang not in ANALYZERS:
            raise ValueError(f"{file}: language must be one of {', '.join(sorted(ANALYZERS))}")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(f"{file}: a task needs a prompt")
        if tid in seen:
            raise ValueError(f"{file}: duplicate task id {tid!r}")
        seen.add(tid)
        try:
            spec = from_dict({**(data.get("spec") or {}), "language": lang}, str(file))
        except SpecError as e:
            raise ValueError(str(e)) from None
        tasks.append(Task(tid, lang, prompt.strip(), spec, str(file)))
    if not tasks:
        raise ValueError(f"{path}: no tasks")
    return tasks


def _rule_words(rule: Rule) -> list[str]:
    out = []
    if rule.syllables:
        counts = ", ".join(str(n) for n in rule.syllables)
        each = "each line has" if len(rule.syllables) == 1 else "lines have, in turn,"
        out.append(
            f"{each} {counts} sung syllables" + (f" (±{rule.tolerance})" if rule.tolerance else "")
        )
    if rule.meter and rule.meter != "free":
        feet = f" with {', '.join(str(f) for f in rule.feet)} stressed beats" if rule.feet else ""
        out.append(f"the meter is {rule.meter}{feet}")
    if rule.rhyme:
        mixed = rule.rhyme != rule.rhyme.upper() and rule.rhyme != rule.rhyme.lower()
        case = "; capital letters end on an unstressed syllable, small ones on a stressed one"
        note = "a dash marks an unrhymed line" + (case if mixed else "")
        out.append(f"the rhyme scheme is {rule.rhyme} ({note})")
    if rule.endings:
        out.append(f"line endings are {rule.endings} (m masculine, f feminine, d dactylic)")
    if rule.forbid_final:
        out.append("no line ends in " + " or ".join(rule.forbid_final))
    return out


def describe(spec: Spec) -> str:
    """The spec in words, for a writer's prompt."""
    parts = []
    base = _rule_words(spec.base)
    if base:
        parts.append("Throughout: " + "; ".join(base) + ".")
    for name, rule in spec.sections.items():
        words = _rule_words(rule)
        if words:
            parts.append(f"In [{name.title()}] sections: " + "; ".join(words) + ".")
    for number, rule in sorted(spec.stanzas.items()):
        words = _rule_words(rule)
        if words:
            parts.append(f"Stanza {number}: " + "; ".join(words) + ".")
    return " ".join(parts)


def brief(task: Task) -> str:
    language = NAMES.get(task.language, task.language)
    return (
        f"{task.prompt}\n\nWrite the lyrics in {language}. Use Suno section tags such as "
        f"[Verse 1] and [Chorus], one sung line per line, nothing but the lyrics.\n\n"
        f"Form: {describe(task.spec)}"
    )


class Writer(Protocol):
    name: str

    def write(self, task: Task) -> str: ...


class DirWriter:
    name = "dir"

    def __init__(self, folder: str | Path) -> None:
        self.folder = Path(folder)

    def write(self, task: Task) -> str:
        path = self.folder / f"{task.id}.txt"
        try:
            return path.read_text(encoding="utf-8")
        except OSError as e:
            raise ProposerError(f"no draft for {task.id}: {e}") from None


class CommandWriter:
    name = "command"

    def __init__(self, argv: list[str], timeout: float = 600.0) -> None:
        self.argv, self.timeout = argv, timeout

    def write(self, task: Task) -> str:
        payload = json.dumps(
            {"id": task.id, "language": task.language, "prompt": task.prompt, "brief": brief(task)},
            ensure_ascii=False,
        )
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
            raise ProposerError(f"writer command failed: {e}") from None
        if done.returncode != 0:
            raise ProposerError(
                f"writer command exited {done.returncode}: {done.stderr.strip()[:300]}"
            )
        return done.stdout


SYSTEM = (
    "You are a lyricist who writes singable song lyrics in the requested language and form. "
    "Answer with the lyrics only."
)


class ClaudeWriter:
    name = "claude"

    def __init__(self, model: str = DEFAULT_MODEL, effort: str = "medium", client=None) -> None:
        self.model, self.effort, self._client = model, effort, client

    @property
    def client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError:
                raise ProposerError(
                    "the Claude writer needs: pip install 'ashugh[claude]'"
                ) from None
            self._client = anthropic.Anthropic()
        return self._client

    def write(self, task: Task) -> str:
        client = self.client
        try:
            response = client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=SYSTEM,
                messages=[{"role": "user", "content": brief(task)}],
                output_config={"effort": self.effort},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except _api_errors() as e:
            raise ProposerError(_describe_api_error(e)) from None
        if response.stop_reason == "refusal":
            raise ProposerError(f"Claude declined task {task.id}")
        return "".join(b.text for b in response.content if getattr(b, "type", "") == "text")


def make_writer(spec: str | None, model: str | None = None, effort: str | None = None) -> Writer:
    import shlex

    spec = spec or "claude"
    if spec == "claude":
        return ClaudeWriter(model or DEFAULT_MODEL, effort or "medium")
    if spec.startswith("cmd:") and spec[4:].strip():
        return CommandWriter(shlex.split(spec[4:]))
    if spec.startswith("dir:") and spec[4:].strip():
        return DirWriter(spec[4:])
    raise ProposerError(f"unknown writer {spec!r}; use claude, cmd:<command> or dir:<folder>")


def metrics(report: Report) -> dict:
    lines = report.lines
    passing = sum(1 for lr in lines if lr.ok)
    codes: dict[str, int] = {}
    for issue in report.issues:
        if issue.severity == "error":
            codes[issue.code] = codes.get(issue.code, 0) + 1
    return {
        "lines": len(lines),
        "passing": passing,
        "line_pass_rate": round(passing / len(lines), 4) if lines else 0.0,
        "song_ok": bool(lines) and report.ok,
        "errors": codes,
    }


def run(
    tasks: list[Task],
    writer: Writer,
    modes: list[str] | tuple[str, ...] = MODES,
    proposer: Proposer | None = None,
    rounds: int = 3,
) -> list[dict]:
    bad = [m for m in modes if m not in MODES]
    if bad:
        raise ValueError(f"unknown mode {bad[0]!r}; use {', '.join(MODES)}")
    if "ashugh" in modes and proposer is None:
        raise ValueError('mode "ashugh" needs a proposer')
    rows = []
    for task in tasks:
        try:
            draft = writer.write(task)
        except ProposerError as e:
            rows.extend(_failed(task, m, str(e)) for m in modes)
            continue
        for mode in modes:
            row = {"task": task.id, "language": task.language, "mode": mode}
            try:
                if mode == "alone":
                    row.update(metrics(scan(draft, task.spec, lang=task.language)), text=draft)
                else:
                    result = fit_song(draft, task.spec, proposer, rounds=rounds, lang=task.language)
                    row.update(
                        metrics(result.report),
                        text=result.text,
                        changes=len(result.changes),
                        rounds=result.rounds,
                        requests=result.requests,
                    )
            except ProposerError as e:
                row = _failed(task, mode, str(e))
            rows.append(row)
    return rows


def _failed(task: Task, mode: str, error: str) -> dict:
    return {
        "task": task.id,
        "language": task.language,
        "mode": mode,
        "error": error,
        "lines": 0,
        "passing": 0,
        "line_pass_rate": 0.0,
        "song_ok": False,
        "errors": {},
    }


def summarize(rows: list[dict]) -> dict:
    out = {}
    for mode in MODES:
        mine = [r for r in rows if r["mode"] == mode]
        if not mine:
            continue
        lines = sum(r["lines"] for r in mine)
        out[mode] = {
            "tasks": len(mine),
            "line_pass_rate": round(sum(r["passing"] for r in mine) / lines, 4) if lines else 0.0,
            "songs_ok": round(sum(r["song_ok"] for r in mine) / len(mine), 4),
            "failed": sum(1 for r in mine if r.get("error")),
        }
    return out


def table(summary: dict) -> str:
    rows = ["mode     tasks  lines passing  songs passing  failed"]
    for mode, s in summary.items():
        lines, songs = f"{s['line_pass_rate']:.1%}", f"{s['songs_ok']:.1%}"
        rows.append(f"{mode:8} {s['tasks']:>5}  {lines:>13}  {songs:>13}  {s['failed']:>6}")
    return "\n".join(rows)
