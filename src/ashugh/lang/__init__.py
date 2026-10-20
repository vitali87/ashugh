"""Language registry and script detection."""

from __future__ import annotations

import re
from types import ModuleType

from ..model import Reading, Syllable, Word
from ..phon import is_vowel
from . import hy, ru

ANALYZERS: dict[str, ModuleType] = {"hy": hy, "ru": ru}
NAMES = {"hy": "Armenian", "ru": "Russian", "xx": "Latin script (rough)"}


def script_of(token: str) -> str:
    for ch in token:
        if hy.is_armenian(ch):
            return "hy"
        if ru.is_cyrillic(ch):
            return "ru"
        if ch.isalpha():
            return "xx"
    return ""


def detect(tokens: list[str]) -> str:
    counts: dict[str, int] = {}
    for t in tokens:
        s = script_of(t)
        if s and s != "xx":
            counts[s] = counts.get(s, 0) + 1
    if not counts:
        return "xx" if any(script_of(t) == "xx" for t in tokens) else ""
    return max(counts, key=lambda k: counts[k])


_LATIN_VOWELS = re.compile(r"[aeiouy]+", re.I)


def latin_word(token: str) -> Word:
    """A rough count for the "oh", "yeah", "la-la" a lyric borrows from English."""
    norm = token.lower()
    groups = list(_LATIN_VOWELS.finditer(norm))
    if len(groups) > 1 and norm.endswith("e") and not norm.endswith(("le", "ee")):
        groups = groups[:-1]
    n = max(1, len(groups))
    cuts = [g.start() - (g.start() > 0 and token[g.start() - 1].isalpha()) for g in groups[1:n]]
    pieces = [token[a:b].strip("-") for a, b in zip([0, *cuts], [*cuts, len(token)])]
    syllables = tuple(Syllable(p) for p in pieces)
    phones = tuple(["a"] * n)
    readings = tuple(Reading(p, phones, norm, "guess") for p in range(n))
    return Word(
        token, norm, "xx", syllables, readings, weak=True, notes=["no analyzer for this script"]
    )


def analyze(lang: str, tokens: list[str], lexicon: dict[str, str]) -> list[Word]:
    """Words of one line; tokens in another script than lang get their own analyzer."""
    words: list[Word] = []
    for token in tokens:
        script = script_of(token)
        if script in ANALYZERS:
            words.append(ANALYZERS[script].analyze_word(token, lexicon))
        else:
            words.append(latin_word(token))
    if lang == "hy" or any(w.lang == "hy" for w in words):
        _armenian_elision(words)
    return words


def _armenian_elision(words: list[Word]) -> None:
    """Mark the schwas that connected speech drops: a vowel before swallows a
    word's leading ը (նա ստացավ -> նաս-տա-ցավ), and a word's final schwa
    syllable links its consonant onto a vowel after it (կյանքն է -> կյանք-նէ)."""

    def first(w: Word) -> str:
        return w.readings[0].phones[0] if w.readings and w.readings[0].phones else ""

    def last(w: Word) -> str:
        return w.readings[0].phones[-1] if w.readings and w.readings[0].phones else ""

    for i, w in enumerate(words):
        w.drop = None
        if w.head_schwa and i > 0 and is_vowel(last(words[i - 1])):
            w.drop = 0
        elif w.tail_schwa and i + 1 < len(words) and _vowel_initial(words[i + 1], first):
            w.drop = w.size - 1


def _vowel_initial(w: Word, first) -> bool:
    # The auxiliary ես is [ɛs], not the pronoun [jɛs], when a linking -ն precedes it.
    return is_vowel(first(w)) or w.norm in hy.AUXILIARIES
