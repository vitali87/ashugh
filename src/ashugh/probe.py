"""probe: measure how Suno pronounces a spelling instead of guessing.

Suno does not document its pronunciation, so ashugh tests it. For each word
you care about, `probe make` writes short lyric clips that differ only in
how the word is spelled (Armenian as script, with its schwas written, or
romanized; Russian plain, with a capital stress vowel, or with an acute).
Generate each clip in Suno, transcribe it with Whisper (`probe transcribe`,
the whisper extra) or any recognizer you name, and `probe score` analyzes the
transcripts with ashugh's own phonology: the spelling whose transcript comes
back closest to the intended sung form wins. The result is a policy file
that `ashugh suno --policy` applies word by word.

A transcript is written in normal spelling, so it shows whether a word came
through intelligibly, not every schwa that was sung; scores measure the
first.
"""

from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import install_hint, lyrics
from .lang import analyze
from .model import ACUTE
from .phon import align_cost, indel_cost

MODES = {"hy": ("script", "schwa", "latin"), "ru": ("plain", "caps", "acute")}
COMMAND_TIMEOUT = 600.0
AUDIO = (".mp3", ".wav", ".m4a", ".flac", ".ogg", ".webm")
OVERRIDE_MARGIN = 0.1


class ProbeError(RuntimeError):
    pass


@dataclass
class Probe:
    id: str
    lang: str
    word: str
    mode: str
    lyrics: str
    sung: str
    syllables: int
    phones: list[str]
    stress: int | None = None


@dataclass
class ScoreResult:
    scores: dict[str, dict[str, float]]
    policy: dict
    missing: list[str] = field(default_factory=list)


def _word(token: str, lang: str):
    words = analyze(lang, lyrics.tokenize(token), {})
    if not words or len({w.norm for w in words}) != 1:  # тихо-тихо counts as one word
        raise ValueError(f"{token!r} is not a single word")
    return words[0]


def make_probes(words: list[str], lang: str, modes: list[str] | None = None) -> list[Probe]:
    from .suno import format_song

    if lang not in MODES:
        raise ValueError(f"probes exist for {', '.join(MODES)}, not {lang!r}")
    words = [w.strip() for w in words if w.strip()]
    if not words:
        raise ValueError("give at least one word to probe")
    modes = list(modes or MODES[lang])
    bad = [m for m in modes if m not in MODES[lang]]
    if bad:
        raise ValueError(f"{lang} probe modes are {', '.join(MODES[lang])}, not {bad[0]!r}")
    plan = []
    for k, token in enumerate(words):
        w = _word(token, lang)
        reading = w.readings[0]
        seen: set[str] = set()
        for mode in modes:
            if lang == "hy":
                shown = format_song(token, armenian=mode, tags=False).text
            else:
                shown = _russian_variant(token, reading.stress, mode)
            if shown in seen:
                continue  # о́блака: caps on the first letter is the acute, one clip is enough
            seen.add(shown)
            line = f"{shown}, {shown}, {shown}"
            plan.append(
                Probe(
                    id=f"{lang}-{k:03d}-{mode}",
                    lang=lang,
                    word=token,
                    mode=mode,
                    lyrics=f"[Verse]\n{line}\n{shown}\n",
                    sung=_word(w.norm, lang).sung() if lang == "hy" else w.sung(reading.stress),
                    syllables=w.size,
                    phones=list(reading.phones),
                    stress=reading.stress,
                )
            )
    return plan


def _russian_variant(token: str, stress: int | None, mode: str) -> str:
    from .suno import _mark_vowel

    plain = "".join(ch.lower() if k > 0 else ch for k, ch in enumerate(token.replace(ACUTE, "")))
    if mode == "plain" or stress is None:
        return plain
    return _mark_vowel(plain, stress, "caps" if mode == "caps" else "acute")


def save_plan(plan: list[Probe], path: str | Path) -> None:
    Path(path).write_text(
        json.dumps([asdict(p) for p in plan], ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_plan(path: str | Path) -> list[Probe]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, list) or not data:
            raise TypeError
        return [Probe(**entry) for entry in data]
    except (OSError, json.JSONDecodeError, TypeError) as e:
        raise ValueError(f"{path}: not a probe plan ({e or 'expected a list of probes'})") from None


def load_transcripts(path: str | Path) -> dict[str, str]:
    """A JSON object {probe id: transcript}, or a directory of <probe id>.txt files."""
    path = Path(path)
    if path.is_dir():
        return {p.stem: p.read_text(encoding="utf-8").strip() for p in sorted(path.glob("*.txt"))}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"{path}: {e}") from None
    if not isinstance(data, dict) or not all(isinstance(v, str) for v in data.values()):
        raise ValueError(f"{path}: expected an object of probe id -> transcript")
    return data


def transcribe(
    clips: str | Path, plan: list[Probe], model: str = "small", engine: str = "whisper"
) -> dict[str, str]:
    """Transcribe <probe id>.<audio> clips with openai-whisper, or with any recognizer
    given as engine="cmd:<command>", where {audio} and {lang} stand for the clip and
    its language and the command prints the transcript."""
    if engine == "whisper":
        hear = _whisper(model)
    elif engine.startswith("cmd:"):
        hear = _command(engine[4:])
    else:
        raise ProbeError(f"unknown engine {engine!r}; use whisper or cmd:<command>")
    clips = Path(clips)
    out = {}
    for p in plan:
        audio = next(
            (clips / f"{p.id}{ext}" for ext in AUDIO if (clips / f"{p.id}{ext}").exists()), None
        )
        if audio is not None:
            out[p.id] = hear(audio, p.lang)
    return out


def _whisper(model: str):
    try:
        import whisper
    except ImportError:
        whisper = None
    if whisper is None:
        raise ProbeError(
            f"transcribing needs Whisper: {install_hint('whisper')}, or --engine cmd:<command>"
        )
    loaded = whisper.load_model(model)
    return lambda audio, lang: loaded.transcribe(str(audio), language=lang)["text"].strip()


def _command(template: str):
    argv = shlex.split(template)
    if not argv:
        raise ProbeError("the transcription command is empty")
    if not any("{audio}" in a for a in argv):
        argv.append("{audio}")

    def hear(audio: Path, lang: str) -> str:
        args = [a.replace("{audio}", str(audio)).replace("{lang}", lang) for a in argv]
        try:
            done = subprocess.run(
                args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",  # a stray byte must not end the run
                timeout=COMMAND_TIMEOUT,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            raise ProbeError(f"transcription command failed on {audio.name}: {e}") from None
        if done.returncode != 0:
            raise ProbeError(
                f"transcription command exited {done.returncode} on {audio.name}: "
                f"{done.stderr.strip()[:200]}"
            )
        text = done.stdout.strip()
        if not text:
            raise ProbeError(f"transcription command printed nothing for {audio.name}")
        return text

    return hear


def _similarity(p: Probe, transcript: str) -> float:
    """How close the transcript's best few words come to the intended sung form."""
    target = tuple(p.phones)
    if not target:
        return 0.0
    full = sum(indel_cost(ph) for ph in target)
    words = analyze(p.lang, lyrics.tokenize(transcript), {}) if transcript else []
    sims = []
    for w in words:
        options = [r for r in w.readings if r.stress == p.stress] or list(w.readings)
        best = min(align_cost(tuple(r.phones), target) for r in options) if options else full
        sims.append(max(0.0, 1.0 - best / full))
    if not sims:
        return 0.0
    top = sorted(sims, reverse=True)[:3]
    return round(sum(top) / len(top), 3)


def score(plan: list[Probe], transcripts: dict[str, str]) -> ScoreResult:
    heard = [p for p in plan if p.id in transcripts]
    if not heard:
        raise ValueError("none of the probes has a transcript")
    missing = [p.id for p in plan if p.id not in transcripts]
    scores: dict[str, dict[str, float]] = {}
    for p in heard:
        scores.setdefault(p.word, {})[p.mode] = _similarity(p, transcripts[p.id])
    policy: dict = {}
    for lang in sorted({p.lang for p in heard}):
        modes = [m for m in MODES[lang] if any(p.mode == m and p.lang == lang for p in heard)]
        words = sorted({p.word for p in heard if p.lang == lang})

        def mean(mode: str, words=words) -> float:
            values = [scores[w][mode] for w in words if mode in scores[w]]
            return sum(values) / len(values) if values else 0.0

        default = max(modes, key=lambda m: (round(mean(m), 6), -modes.index(m)))
        overrides = {}
        for w in words:
            best = max(scores[w], key=lambda m: (scores[w][m], -modes.index(m)))
            if best != default and scores[w][best] - scores[w].get(default, 0.0) > OVERRIDE_MARGIN:
                overrides[_word(w, lang).norm] = best
        policy[lang] = {"default": default, "words": overrides}
    return ScoreResult(scores, policy, missing)
