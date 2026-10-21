"""Language registry and script detection."""

from __future__ import annotations

import re
import unicodedata
from types import ModuleType

from .. import lyrics
from ..model import Reading, Syllable, Word
from ..phon import is_vowel
from . import en, hy, ru

ANALYZERS: dict[str, ModuleType] = {"hy": hy, "ru": ru, "en": en}
NAMES = {"hy": "Armenian", "ru": "Russian", "en": "English", "xx": "unsupported script"}


AMPERSAND = {"en": "and", "ru": "и", "hy": "և"}


def analyze_word_as(token: str, lexicon: dict[str, str]) -> Word:
    """One word by its own script's analyzer."""
    script = script_of(token)
    return (
        ANALYZERS[script].analyze_word(token, lexicon)
        if script in ANALYZERS
        else foreign_word(token)
    )


def script_of(token: str) -> str:
    for ch in token:
        if hy.is_armenian(ch):
            return "hy"
        if ru.is_cyrillic(ch):
            return "ru"
        if en.is_latin(ch):
            return "en"
        if ch.isalpha():
            return "xx"
    return ""


def override_error(word: str, value: str) -> str | None:
    """Why a [lexicon] entry cannot be used, by the script of its word; None if
    it can, or if no analyzer reads that script."""
    module = ANALYZERS.get(script_of(word))
    return module.override_error(word, value) if module else None


def detect(tokens: list[str]) -> str:
    counts: dict[str, int] = {}
    for t in tokens:
        s = script_of(t)
        if s and s != "xx":
            counts[s] = counts.get(s, 0) + 1
    if not counts:
        return "xx" if any(script_of(t) == "xx" for t in tokens) else ""
    return max(counts, key=lambda k: counts[k])


# Vowel letters of scripts ashugh does not analyze, by their base letter: Latin
# (with any accent), Greek, Georgian.
FOREIGN_VOWELS = frozenset("aeiouyæøœαεηιοωυაეიოუ")


def _vowel_groups(norm: str) -> list[re.Match]:
    marks = "".join(
        "v" if unicodedata.normalize("NFD", ch)[:1] in FOREIGN_VOWELS else "c" for ch in norm
    )
    return list(re.finditer("v+", marks))


def foreign_word(token: str) -> Word:
    """A rough vowel-group count for a word in a script ashugh does not analyze."""
    norm = token.lower()
    groups = _vowel_groups(norm)
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


PHRASE_END = re.compile(r"\s*[,.;:!?…—–։՝]")


def analyze(
    lang: str, tokens: list[str], lexicon: dict[str, str], text: str | None = None
) -> list[Word]:
    """Words of one line; tokens in another script than lang get their own analyzer.
    With the line's text, a preposition before a comma or full stop is stressed
    like one at the end of the line: hold on, hold on."""
    words: list[Word] = []
    letters = "".join(ch for t in tokens for ch in t if ch.isalpha())
    capitals = len(letters) > 3 and letters.isupper()  # I AM HERE: am, not A.M.
    for token in tokens:
        if token == "&":  # rock & roll: the line's own and
            and_ = analyze_word_as(AMPERSAND.get(lang, "and"), lexicon)
            and_.text = token
            words.append(and_)
            continue
        script = script_of(token)
        if script == en.CODE:
            words.append(en.analyze_word(token, lexicon, capitals))
        elif script in ANALYZERS:
            words.append(ANALYZERS[script].analyze_word(token, lexicon))
        else:
            words.append(foreign_word(token))
    if lang == "hy" or any(w.lang == "hy" for w in words):
        _armenian_elision(words)
    if any(w.lang == "ru" for w in words):
        ru.second_locatives(words)
        ru.preposition_shift(words)
    end = words[-1] if words else None
    if end is not None and end.lang == "en" and end.clitic and end.norm not in ("a", "an", "the"):
        end.clitic = False  # a stranded preposition is stressed: gone by, roll in
    before = words[-2] if len(words) > 1 else None
    if end is not None and before is not None and end.lang == before.lang == "en":
        if end.norm in en.OBJECTS and not (before.clitic or before.norm in en.WEAK):
            end.enclitic = end.free_end = True  # need it, hold me, missing yóu on a beat
        content = words[-3] if len(words) > 2 else None
        if (
            end.norm in en.OBJECTS
            and before.norm in en.PREPOSITIONS
            and content is not None
            and content.lang == "en"
            and not (content.clitic or content.norm in en.WEAK)
        ):
            end.enclitic = end.free_end = True  # cáll to me; or back to mé on a beat
    ends = [False] * len(words)
    if text is not None:
        spans = lyrics.token_spans(text)
        for k, (w, (_, stop, _)) in enumerate(zip(words, spans)):
            ends[k] = bool(PHRASE_END.match(text, stop))
            if w.lang == "en" and w.norm in en.PARTICLES and ends[k]:
                w.clitic = False
    if ends:
        ends[-1] = True
    norms = [w.norm for w in words]
    for k, w in enumerate(words):
        if w.lang == "hy" and w.norm == "ես":
            hy.read_es(w, hy.auxiliary_es(norms, k, ends))
    return words


def _armenian_elision(words: list[Word]) -> None:
    """Mark the schwas that connected speech drops: a vowel before swallows a
    word's leading ը (նա ստացավ -> նաս-տա-ցավ), and a word's final schwa
    syllable links its consonant onto a vowel after it (կյանքն է -> կյանք-նէ).
    Elsewhere, a compound's inner schwa may drop (լու-սան-կար)."""

    def first(w: Word) -> str:
        return w.readings[0].phones[0] if w.readings and w.readings[0].phones else ""

    def last(w: Word) -> str:
        return w.readings[0].phones[-1] if w.readings and w.readings[0].phones else ""

    for i, w in enumerate(words):
        if w.lang != "hy":
            continue
        w.drop = w.optional
        if w.head_schwa and i > 0 and is_vowel(last(words[i - 1])):
            w.drop = 0
        elif w.tail_schwa and i + 1 < len(words) and _vowel_initial(words[i + 1], first):
            w.drop = w.size - 1


def _vowel_initial(w: Word, first) -> bool:
    # The auxiliary ես is [ɛs], not the pronoun [jɛs], when a linking -ն precedes it.
    return is_vowel(first(w)) or w.norm in hy.AUXILIARIES
