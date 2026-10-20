"""suno: rewrite lyrics into a form Suno sings the way they are meant.

* Russian: ё is restored where the dictionary is sure (еще -> ещё), and
  stress is marked only on words whose stress is ambiguous or unknown, by a
  capital vowel (зАмок, the convention Suno users rely on) or an acute.
* Armenian: kept in script, written with every sung schwa spelled out
  (ըսպասում, Մըկըրտիչ), or romanized phonetically (əspasum, Məkərtich).
  A probe policy (ashugh probe score) can pick the mode word by word.
* Held notes: the last word of each line, or every word, split into its
  sung syllables (пра-вил).
* Section tags: translated to the names Suno knows ([Припев] -> [Chorus]);
  an untagged song gets [Verse n] and [Chorus] from its repeated stanzas.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import lyrics
from .model import ACUTE, LICENCES, Word
from .scan import LineReport, Report, scan
from .spec import Spec

STRESS_MODES = ("caps", "acute", "none")
ARMENIAN_MODES = ("script", "schwa", "latin")
SPLIT_MODES = ("none", "last", "all")
RUSSIAN_PROBES = ("plain", "caps", "acute")  # probe modes, mapped to stress marks below
PROBE_STRESS = {"plain": "none", "caps": "caps", "acute": "acute"}
RU_VOWELS = set("аеёиоуыэюя")

LATIN = {
    "a": "a",
    "e": "e",
    "i": "i",
    "o": "o",
    "u": "u",
    "b": "b",
    "g": "g",
    "d": "d",
    "z": "z",
    "tʰ": "t",
    "ʒ": "zh",
    "l": "l",
    "χ": "kh",
    "ts": "ts",
    "k": "k",
    "h": "h",
    "dz": "dz",
    "ʁ": "gh",
    "tʃ": "ch",
    "m": "m",
    "j": "y",
    "n": "n",
    "ʃ": "sh",
    "tʃʰ": "ch",
    "p": "p",
    "dʒ": "j",
    "r": "rr",
    "s": "s",
    "v": "v",
    "t": "t",
    "ɾ": "r",
    "tsʰ": "ts",
    "pʰ": "p",
    "kʰ": "k",
    "f": "f",
}

TAGS = lyrics.SECTION_NAMES
TAG_RE = re.compile(
    r"^(\s*)\[\s*([^\]:\d]*?)\s*((?:[xх×]\s*)?\d+(?:\s*[xх×])?|)\s*(:[^\]]*)?\]\s*$", re.I
)


@dataclass
class Note:
    line: int
    kind: str  # yo | stress | armenian | split | tag
    word: str
    new: str
    why: str = ""


@dataclass
class SunoResult:
    text: str
    notes: list[Note] = field(default_factory=list)


def load_policy(path: str | Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"{path}: {e}") from None
    check_policy(data)
    return data


def check_policy(policy: dict) -> None:
    if not isinstance(policy, dict):
        raise ValueError("a policy is an object keyed by language")
    for lang, allowed, fallback in (
        ("hy", ARMENIAN_MODES, "script"),
        ("ru", RUSSIAN_PROBES, "plain"),
    ):
        entry = policy.get(lang, {})
        if not isinstance(entry, dict):
            raise ValueError(f'policy "{lang}" must be an object')
        modes = [entry.get("default", fallback), *(entry.get("words") or {}).values()]
        bad = [m for m in modes if m not in allowed]
        if bad:
            raise ValueError(f"{lang} policy modes must be {', '.join(allowed)}, not {bad[0]!r}")


def format_song(
    text: str,
    spec: Spec | None = None,
    stress: str = "caps",
    armenian: str = "script",
    split: str = "none",
    schwa: str = "ə",
    tags: bool = True,
    policy: dict | None = None,
    lang: str | None = None,
) -> SunoResult:
    if stress not in STRESS_MODES:
        raise ValueError(f"stress must be one of {', '.join(STRESS_MODES)}")
    if armenian not in ARMENIAN_MODES:
        raise ValueError(f"armenian must be one of {', '.join(ARMENIAN_MODES)}")
    if split not in SPLIT_MODES:
        raise ValueError(f"split must be one of {', '.join(SPLIT_MODES)}")
    if not schwa or not schwa.isalpha():
        raise ValueError("schwa must be a letter, e.g. ə or e")
    if policy is not None:
        check_policy(policy)
    words_policy = ((policy or {}).get("hy") or {}).get("words") or {}
    default_mode = ((policy or {}).get("hy") or {}).get("default", armenian) if policy else armenian
    ru_words: dict[str, str] = {}
    if policy and "ru" in policy:
        stress = PROBE_STRESS[policy["ru"].get("default", "plain")]
        ru_words = {w: PROBE_STRESS[m] for w, m in (policy["ru"].get("words") or {}).items()}

    report = scan(text, spec or Spec(), lang=lang)
    raw = lyrics.split_lines(text, keepends=True)
    notes: list[Note] = []
    for lr in report.lines:
        line_raw = raw[lr.line.number - 1]
        body, ending = _split_ending(line_raw)
        spans = lyrics.token_spans(body)
        elided = _elided(lr)
        pieces, last = [], 0
        for i, ((a, b, token), word) in enumerate(zip(spans, lr.line.words)):
            pieces.append(body[last:a])
            hold = split == "all" or (split == "last" and i == len(spans) - 1)
            mode = words_policy.get(word.norm, default_mode)
            how = ru_words.get(word.norm, stress)
            new = _render(word, token, lr, i, i in elided, how, mode, hold, schwa, notes)
            pieces.append(new)
            last = b
        pieces.append(body[last:])
        raw[lr.line.number - 1] = "".join(pieces) + ending
    out = "".join(raw)
    if tags:
        out = _retag(out, report, notes)
    return SunoResult(out, notes)


def _split_ending(line: str) -> tuple[str, str]:
    stripped = line.rstrip("\r\n")
    return stripped, line[len(stripped) :]


def _elided(lr: LineReport) -> set[int]:
    """Schwas to drop: whatever the slot's count needed, a compound's that the
    meter left out, and every linking -ն."""
    words = lr.line.words
    out = set(lr.fit.elided) if lr.target is not None else set()
    out |= {
        i
        for i in lr.fit.elided
        if words[i].optional is not None and words[i].drop == words[i].optional
    }
    out |= {
        i
        for i, w in enumerate(lr.line.words)
        if w.drop is not None and w.drop == w.size - 1 and w.size > 1
    }
    return out


def _render(
    w: Word,
    token: str,
    lr: LineReport,
    i: int,
    dropped: bool,
    stress: str,
    mode: str,
    hold: bool,
    schwa: str,
    notes: list[Note],
) -> str:
    n = lr.line.number
    if w.lang == "ru":
        new = _russian(w, token, lr.fit.stresses.get(i), stress, n, notes)
        return _hyphenate(new, [len(s.text) for s in w.syllables]) if hold and w.size > 1 else new
    if w.lang == "hy":
        return _armenian(w, token, dropped, mode, hold, schwa, n, notes)
    if hold and w.size > 1:
        return "-".join(s.text for s in w.syllables)
    return token


def _russian(
    w: Word, token: str, chosen: int | None, stress: str, n: int, notes: list[Note]
) -> str:
    if ACUTE in token and stress == "none":
        return token  # the writer's own marks stay as written
    letters = token.replace(ACUTE, "")
    marked_by_writer = letters != token
    candidates = [r for r in w.readings if r.stress == chosen] or list(w.readings)
    spellings = {r.spelling for r in w.readings if r.source not in LICENCES}
    new = letters
    if len(spellings) == 1 and "ё" in candidates[0].spelling:
        target = candidates[0].spelling.replace("-", "")
        flat = [k for k, ch in enumerate(letters) if ch != "-"]
        if len(flat) == len(target):
            chars = list(letters)
            for k, ch in zip(flat, target):
                if ch == "ё" and chars[k].lower() == "е":
                    chars[k] = "Ё" if chars[k].isupper() else "ё"
            if "".join(chars) != letters:
                new = "".join(chars)
                notes.append(Note(n, "yo", token, new, "ё restored"))
    hint = w.ambiguous or w.guessed or marked_by_writer
    if stress != "none" and w.size > 1 and chosen is not None and hint:
        marked = _mark_vowel(new, chosen, stress)
        if marked != new:
            if marked_by_writer:
                why = "marked in the lyrics"
            else:
                why = "stress guessed by the meter" if w.guessed else "ambiguous stress"
            notes.append(Note(n, "stress", token, marked, why))
            new = marked
    return new


def _mark_vowel(token: str, syllable: int, stress: str) -> str:
    count = -1
    for k, ch in enumerate(token):
        if ch.lower() in RU_VOWELS:
            count += 1
            if count == syllable:
                if ch.lower() == "ё":
                    return token
                if stress == "caps" and k > 0:  # a capital first letter reads as case
                    return token[:k] + ch.upper() + token[k + 1 :]
                return token[: k + 1] + ACUTE + token[k + 1 :]
    return token


def _hyphenate(token: str, lengths: list[int]) -> str:
    """Hyphens between sung syllables; lengths count letters, not marks or hyphens."""
    cuts, total = set(), 0
    for length in lengths[:-1]:
        total += length
        cuts.add(total)
    out, seen = [], 0
    for ch in token:
        if ch not in (ACUTE, "-") and seen in cuts and out and out[-1] != "-":
            out.append("-")
            cuts.discard(seen)
        out.append(ch)
        if ch not in (ACUTE, "-"):
            seen += 1
    return "".join(out)


def _armenian(
    w: Word,
    token: str,
    dropped: bool,
    mode: str,
    hold: bool,
    schwa: str,
    n: int,
    notes: list[Note],
) -> str:
    drop = w.drop if dropped else None
    if mode == "latin":
        parts = [_latin(s.phones, k == drop, schwa) for k, s in enumerate(w.syllables)]
    elif mode == "schwa":
        parts = [
            s.text.replace("ը", "", 1).replace("Ը", "", 1) if k == drop else s.text
            for k, s in enumerate(w.syllables)
        ]
    else:
        parts = [_written(s.text, s.epenthetic) for s in w.syllables]
    parts = _merge_vowelless(parts, mode)
    new = ("-" if hold else "").join(parts)
    if mode == "latin":
        new = _case_like(token, new)
    if mode == "script" and not hold:
        return token
    if new != token:
        notes.append(Note(n, "armenian" if mode != "script" else "split", token, new, mode))
    return new


def _written(text: str, epenthetic: bool) -> str:
    """A syllable as written: its hidden ը taken back out."""
    return text.replace("ը", "", 1).replace("Ը", "", 1) if epenthetic else text


def _latin(phones: tuple[str, ...], dropped: bool, schwa: str) -> str:
    out = []
    for ph in phones:
        if ph == "ə":
            if not dropped:
                out.append(schwa)
            continue
        out.append(LATIN.get(ph, ph))
    return "".join(out)


def _merge_vowelless(parts: list[str], mode: str) -> list[str]:
    vowels = "aeiouəy" if mode == "latin" else "աեէըիոօւ"
    merged: list[str] = []
    for p in parts:
        has_vowel = any(ch.lower() in vowels for ch in p)
        if merged and not has_vowel:
            merged[-1] += p
        elif not merged or any(ch.lower() in vowels for ch in merged[-1]):
            merged.append(p)
        else:
            merged[-1] += p
    return [p for p in merged if p]


def _case_like(token: str, latin: str) -> str:
    letters = [ch for ch in token if ch.isalpha()]
    if letters and all(ch.isupper() for ch in letters) and len(letters) > 1:
        return latin.upper()
    if token[:1].isupper():
        return latin[:1].upper() + latin[1:]
    return latin


def _retag(text: str, report: Report, notes: list[Note]) -> str:
    raw = lyrics.split_lines(text, keepends=True)
    tagged = False
    for k, line in enumerate(raw):
        m = TAG_RE.match(line.rstrip("\r\n"))
        if not m:
            continue
        tagged = True
        lead, name, number, extra = m.group(1), m.group(2), m.group(3), m.group(4) or ""
        known = TAGS.get(name.strip().lower())
        if known:
            new = f"{lead}[{known}{' ' + number if number else ''}{extra}]"
            ending = line[len(line.rstrip("\r\n")) :]
            if new != line.rstrip("\r\n"):
                notes.append(Note(k + 1, "tag", line.strip(), new.strip()))
            raw[k] = new + ending
    if tagged or not report.lines:
        return "".join(raw)
    return _infer_tags(raw, report, notes)


def _infer_tags(raw: list[str], report: Report, notes: list[Note]) -> str:
    stanzas: dict[int, list[LineReport]] = {}
    for lr in report.lines:
        stanzas.setdefault(lr.line.unit, []).append(lr)
    texts = {
        u: tuple(" ".join(lr.line.text.lower().split()) for lr in lrs) for u, lrs in stanzas.items()
    }
    repeated = {t for t in texts.values() if list(texts.values()).count(t) > 1}
    verses = sum(1 for t in texts.values() if t not in repeated)
    starts: dict[int, str] = {}
    verse_no = 0
    for u, lrs in stanzas.items():
        if texts[u] in repeated:
            tag = "[Chorus]"
        else:
            verse_no += 1
            tag = f"[Verse {verse_no}]" if verses > 1 else "[Verse]"
        starts[lrs[0].line.number] = tag
    out = []
    for k, line in enumerate(raw, 1):
        if k in starts:
            out.append(starts[k] + "\n")
            notes.append(Note(k, "tag", "", starts[k], "inferred from repeated stanzas"))
        out.append(line)
    return "".join(out)
