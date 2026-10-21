"""Data types shared by the analyzers, the meter and rhyme engines and the reports."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .phon import is_vowel

# Readings that verse allows but speech does not insist on: a compound's stress on its
# second part (sometíme), a noun leaving its stress to the preposition (по́ лесу), a
# late stress moving back before a stressed word (Ténnessee whiskey).
LICENCES = frozenset({"shift", "lean", "clash"})
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
    source: str  # mark | user | lexicon | rule | guess | clitic, or a licence
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
    free_end: bool = False  # a line-final pronoun after a preposition: a foot if on a beat
    spelled: bool = False  # an abbreviation sung letter by letter (L-A), never hyphenated
    head_schwa: bool = False  # starts with a schwa that a vowel before it can swallow
    tail_schwa: bool = False  # ends in a schwa syllable whose consonant can link forward
    drop: int | None = None  # syllable whose schwa may drop in this line's context
    optional: int | None = None  # a schwa syllable that may drop anywhere (a compound's)
    drop_cost: float = 0.0  # what dropping costs the meter: nothing for ev'ry, a licence for mem'ry
    short_readings: tuple[Reading, ...] = ()  # dictionary readings sung short: our as are
    optional_why: str = ""  # why the optional schwa may go, for the note
    notes: list[str] = field(default_factory=list)
    held: bool = False  # one held vowel (Ооо, աաա): a vocable, no rhyme word after a word
    assumed: str = ""  # how a name the dictionary lacks was read: perse + phone

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
    def leans(self) -> bool:
        """May lend its stress to the preposition before it."""
        return any(r.source == "lean" for r in self.readings)

    @property
    def guessed(self) -> bool:
        return any(r.source == "guess" for r in self.readings)

    @property
    def ambiguous(self) -> bool:
        """More than one stress the language allows, not counting verse licences."""
        return len({r.stress for r in self.readings if r.source not in LICENCES}) > 1

    def sung(self, stress: int | None = None, mark: bool = False, dropped: bool = False) -> str:
        """Syllables joined by hyphens; with dropped, the droppable one as the line
        sings it: an Armenian schwa in brackets (սե-ր(ը)ն), an English syllable run
        into the one before it (fi-re), or the one after it before an r (ev-ery)."""
        if not self.syllables:
            return self.text
        parts = []
        # a capital opening a part is no mark: Փարիզ-Երևան, Д'Артаньян
        caps = [
            ch for k, ch in enumerate(self.text[1:]) if ch.isupper() and self.text[k] not in "-'’"
        ]
        # замОк: the writer's capital mark, shown by the acute as every other is
        writer_caps = (
            mark
            and len(caps) == 1
            and caps[0].lower() in VOWEL_LETTERS
            and not self.text.isupper()  # ՏԱ, ДА: a word in capitals marks nothing
        )
        for i, text in enumerate(self._with_yo(stress)):
            if writer_caps:
                text = text[:1] + text[1:].lower() if i == 0 else text.lower()
            if mark and i == stress and self.size > 1:
                text = mark_stress(text)
            parts.append(text)
        d = self.drop
        if dropped and d is not None and 0 <= d < len(parts) and len(parts) > 1:
            if "ը" in parts[d] or "Ը" in parts[d]:
                parts[d] = parts[d].replace("ը", "(ը)", 1).replace("Ը", "(Ը)", 1)
            elif "ə" in parts[d]:  # kyan-k(ə)n: Armenian typed in Latin
                parts[d] = parts[d].replace("ə", "(ə)", 1)
            else:  # ev-ery, his-tory: a vowel dropped before an r goes with the r
                ahead = d + 1 < len(parts) and parts[d + 1][:1] in ("r", "R")
                # strug-gl-ing sung strug-gling: a syllable with no vowel letter goes
                # into the vowel after it
                ahead = ahead or (
                    d + 1 < len(parts)
                    and not re.search(r"(?i)[aeiouy]", parts[d])
                    and parts[d + 1][:1].lower() in "aeiouy"
                )
                at = d if ahead or d == 0 else d - 1
                parts[at : at + 2] = ["".join(parts[at : at + 2])]
        return "-".join(parts)

    def _with_yo(self, stress: int | None) -> list[str]:
        """The syllables with the ё their reading has where the text writes е: мо-ё."""
        texts = [s.text for s in self.syllables]
        spelling = self.reading(stress).spelling.replace("-", "") if self.readings else ""
        flat = "".join(texts)
        if "ё" not in spelling or flat.lower().replace("ё", "е") != spelling.replace("ё", "е"):
            return texts
        letters = [
            ("Ё" if ch == "Е" else "ё") if ch in "еЕ" and spelling[k] == "ё" else ch
            for k, ch in enumerate(flat)
        ]
        out, at = [], 0
        for t in texts:
            out.append("".join(letters[at : at + len(t)]))
            at += len(t)
        return out


VOWEL_LETTERS = set("аеёиоуыэюяaeiouyաեէըիոօև")


def mark_stress(text: str) -> str:
    """text with an acute after its first vowel letter (ё needs none)."""
    for i, ch in enumerate(text):
        if ch.lower() == "y" and text[i + 1 : i + 2].lower() in VOWEL_LETTERS - {"y"}:
            continue  # yes, be-yond, kyan: a y before a vowel is a glide
        # a Latin vowel under a diacritic (ï, é), not й, whose breve makes no vowel
        parts = unicodedata.normalize("NFD", ch.lower()) if ord(ch) < 0x250 else ch.lower()
        if parts[0] in VOWEL_LETTERS and ch.lower() != "ё":
            if ACUTE in parts:
                return text  # fé: written with its acute already
            return text[: i + 1] + ACUTE + text[i + 1 :]  # na-ḯve keeps its diaeresis
        if ch.lower() == "ё":
            return text
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
