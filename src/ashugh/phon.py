"""Phoneme features shared by the language analyzers and the rhyme scorer.

Phonemes are short IPA strings. A consonant may carry "ʰ" (aspirated, Armenian)
or "ʲ" (palatalized, Russian); everything else about it comes from BASE. English
diphthongs are single vowel phonemes ("aɪ", "oʊ").
"""

from __future__ import annotations

from functools import cache
from typing import NamedTuple

VOWELS = frozenset(
    ["a", "e", "i", "o", "u", "ə", "ɨ", "ɪ"]  # Armenian, Russian
    + ["æ", "ɑ", "ɔ", "ʌ", "ɛ", "ʊ", "ɝ", "ɚ", "aɪ", "aʊ", "eɪ", "oʊ", "ɔɪ"]  # English
)

# manner, place, voiced
BASE: dict[str, tuple[str, str, bool]] = {
    "p": ("stop", "lab", False),
    "b": ("stop", "lab", True),
    "t": ("stop", "cor", False),
    "d": ("stop", "cor", True),
    "k": ("stop", "dor", False),
    "g": ("stop", "dor", True),
    "ts": ("affr", "cor", False),
    "dz": ("affr", "cor", True),
    "tʃ": ("affr", "pal", False),
    "dʒ": ("affr", "pal", True),
    "f": ("fric", "lab", False),
    "v": ("fric", "lab", True),
    "s": ("fric", "cor", False),
    "z": ("fric", "cor", True),
    "ʃ": ("fric", "pal", False),
    "ʒ": ("fric", "pal", True),
    "ɕ": ("fric", "pal", False),
    "x": ("fric", "dor", False),
    "χ": ("fric", "dor", False),
    "ʁ": ("fric", "dor", True),
    "h": ("fric", "glot", False),
    "θ": ("fric", "cor", False),
    "ð": ("fric", "cor", True),
    "m": ("nas", "lab", True),
    "n": ("nas", "cor", True),
    "ŋ": ("nas", "dor", True),
    "l": ("liq", "cor", True),
    "ɾ": ("liq", "cor", True),
    "r": ("liq", "cor", True),
    "ɹ": ("liq", "cor", True),
    "j": ("glide", "pal", True),
    "w": ("glide", "lab", True),
}

SONORITY = {"stop": 1, "affr": 1, "fric": 2, "nas": 3, "liq": 4, "glide": 5}


class Features(NamedTuple):
    base: str
    manner: str
    place: str
    voiced: bool
    aspirated: bool
    palatal: bool


def is_vowel(ph: str) -> bool:
    return ph in VOWELS


@cache
def features(ph: str) -> Features:
    base = ph.replace("ʰ", "").replace("ʲ", "").replace("ː", "")
    manner, place, voiced = BASE[base]
    return Features(base, manner, place, voiced, "ʰ" in ph, "ʲ" in ph)


def sonority(ph: str) -> int:
    if ph in VOWELS:
        return 6
    return SONORITY[features(ph).manner]


def is_obstruent(ph: str) -> bool:
    return ph not in VOWELS and features(ph).manner in ("stop", "affr", "fric")


def is_stop(ph: str) -> bool:
    return ph not in VOWELS and features(ph).manner in ("stop", "affr")


_CLOSE_VOWELS = {
    frozenset("aə"): 0.2,
    frozenset("iɪ"): 0.2,
    frozenset("eɪ"): 0.25,
    frozenset("iɨ"): 0.1,
    frozenset("əɪ"): 0.3,
    frozenset("ɨɪ"): 0.25,
    frozenset("oə"): 0.35,
    frozenset("eə"): 0.4,
    frozenset(("ɝ", "ɚ")): 0.1,
    frozenset(("ʌ", "ə")): 0.2,
    frozenset(("ɑ", "ɔ")): 0.2,
    frozenset(("ʊ", "u")): 0.35,
    frozenset(("ɛ", "æ")): 0.4,
    frozenset(("ɛ", "eɪ")): 0.4,
    frozenset(("ɔ", "oʊ")): 0.4,
}


def vowel_distance(a: str, b: str) -> float:
    if a == b:
        return 0.0
    return _CLOSE_VOWELS.get(frozenset((a, b)), 0.7)


def consonant_distance(a: str, b: str) -> float:
    if a == b:
        return 0.0
    fa, fb = features(a), features(b)
    if fa.base == fb.base:
        return 0.15
    if fa.manner == fb.manner and fa.place == fb.place:
        return 0.2
    front = ("cor", "pal")
    if {fa.manner, fb.manner} == {"stop", "affr"} and fa.place in front and fb.place in front:
        return 0.45  # ветер / вечер
    if fa.manner == fb.manner:
        return 0.5
    if fa.place == fb.place:
        return 0.65
    return 0.85


def distance(a: str, b: str) -> float:
    va, vb = a in VOWELS, b in VOWELS
    if va and vb:
        return vowel_distance(a, b)
    if va or vb:
        return 1.0
    return consonant_distance(a, b)


def indel_cost(ph: str) -> float:
    if ph in VOWELS:
        return 0.8
    if ph in ("j", "h"):
        return 0.3
    return 0.5


def align_cost(xs: tuple[str, ...], ys: tuple[str, ...]) -> float:
    """Weighted edit distance between two phoneme sequences."""
    prev = [0.0]
    for y in ys:
        prev.append(prev[-1] + indel_cost(y))
    for x in xs:
        cur = [prev[0] + indel_cost(x)]
        for j, y in enumerate(ys, 1):
            cur.append(
                min(
                    prev[j] + indel_cost(x),
                    cur[j - 1] + indel_cost(y),
                    prev[j - 1] + distance(x, y),
                )
            )
        prev = cur
    return prev[-1]
