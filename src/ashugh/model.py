"""Data types shared by the analyzers, the meter and rhyme engines and the reports."""

from __future__ import annotations

from dataclasses import dataclass, field

from .phon import is_vowel

ACUTE = "\u0301"


@dataclass(frozen=True)
class Syllable:
    text: str  # sung spelling in the source script, hidden vowels written out
    epenthetic: bool = False  # its vowel is not written (Armenian hidden ը)
    phones: tuple[str, ...] = ()  # this syllable's phonemes, where the analyzer knows them


@dataclass(frozen=True)
class Reading:
    """One way to say a word: where its stress falls and what it sounds like."""

    stress: int | None  # stressed syllable, None for a word with no stress of its own
    phones: tuple[str, ...]  # the n-th vowel here is the nucleus of syllable n
    spelling: str  # normalized spelling, ё restored for Russian
    source: str  # mark | user | lexicon | rule | guess | clitic
    secondary: tuple[int, ...] = ()  # syllables with secondary stress (English)
    penalty: float = 0.0  # meter cost of choosing this reading (a guess the prior disfavors)


@dataclass
class Word:
    text: str
    norm: str
    lang: str
    syllables: tuple[Syllable, ...]
    readings: tuple[Reading, ...]
    weak: bool = False  # metrically free: may take a weak or a strong beat
    clitic: bool = False  # no stress of its own (prepositions, "and", auxiliaries)
    enclitic: bool = False  # leans on the word before it, so rhymes with it
    head_schwa: bool = False  # starts with a schwa that a vowel before it can swallow
    tail_schwa: bool = False  # ends in a schwa syllable whose consonant can link forward
    drop: int | None = None  # syllable whose schwa may drop in this line's context
    notes: list[str] = field(default_factory=list)

    @property
    def size(self) -> int:
        return len(self.syllables)

    def stress_options(self) -> list[int | None]:
        seen: list[int | None] = []
        for r in self.readings:
            if r.stress not in seen:
                seen.append(r.stress)
        return seen

    def reading(self, stress: int | None) -> Reading:
        for r in self.readings:
            if r.stress == stress:
                return r
        return self.readings[0]

    @property
    def guessed(self) -> bool:
        return any(r.source == "guess" for r in self.readings)

    @property
    def ambiguous(self) -> bool:
        """More than one stress the language allows, not counting verse licences."""
        return len({r.stress for r in self.readings if r.source != "shift"}) > 1

    def sung(self, stress: int | None = None, mark: bool = False) -> str:
        if not self.syllables:
            return self.text
        parts = []
        for i, syl in enumerate(self.syllables):
            text = syl.text
            if mark and i == stress and self.size > 1:
                text = _mark(text)
            parts.append(text)
        return "-".join(parts)


VOWEL_LETTERS = set("аеёиоуыэюяaeiouyաեէըիոօ")


def _mark(text: str) -> str:
    for i, ch in enumerate(text):
        if ch.lower() in VOWEL_LETTERS:
            if ch.lower() == "ё":
                return text
            return text[: i + 1] + ACUTE + text[i + 1 :]
    return text


def nuclei(phones: tuple[str, ...]) -> list[int]:
    return [i for i, ph in enumerate(phones) if is_vowel(ph)]


@dataclass
class Line:
    number: int  # 1-based line number in the source file
    text: str
    section: str  # the tag as written, e.g. "Verse 1"
    key: str  # the tag normalized for spec lookup, e.g. "verse"
    unit: int  # stanza id: a new one starts at every tag and blank line
    index: int  # position inside the stanza
    lang: str = ""
    words: list[Word] = field(default_factory=list)

    @property
    def count(self) -> int:
        return sum(w.size for w in self.words)
