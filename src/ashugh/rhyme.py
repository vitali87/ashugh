"""Rhyme by sound: tails, scores, and schemes.

A line's rhyme tail starts at its last stressed vowel and runs to the end of
the line, so enclitics count (Armenian սիրում եմ rhymes on -ում եմ). Two tails
rhyme when their stressed vowels match and what follows sounds alike; an open
masculine rhyme (стоят на гласной: ты / красоты) also needs the consonant
before the vowel to match.

Scores fall into levels: perfect >= 0.9, near >= 0.7, slant >= 0.45,
assonance >= 0.25, none below.
"""

from __future__ import annotations

from dataclasses import dataclass

from .meter import Fit, _anchor, slots
from .model import Line, nuclei
from .phon import align_cost, distance, is_vowel, vowel_distance

LEVELS = (("perfect", 0.9), ("near", 0.7), ("slant", 0.45), ("assonance", 0.25), ("none", 0.0))
THRESHOLD = dict(LEVELS)
POST_TONIC_VOWELS = 0.5  # weight of vowel differences after the stressed vowel


@dataclass(frozen=True)
class Tail:
    onset: tuple[str, ...]
    vowel: str
    rest: tuple[str, ...]
    post: int  # syllables after the stressed one
    word: str  # the rhyming word(s) as written
    spelling: str
    lang: str = ""

    @property
    def sound(self) -> str:
        return "".join(self.onset[-1:]) + self.vowel + "".join(self.rest)


def level(score: float) -> str:
    for name, floor in LEVELS:
        if score >= floor:
            return name
    return "none"


def anchor_word(line: Line, fit: Fit) -> int | None:
    """Index of the word carrying the line's last stress."""
    ss = slots(line.words, fit.elided)
    k = _anchor(ss)
    return ss[k].word if k is not None else None


def tails(line: Line, fit: Fit) -> list[Tail]:
    """Rhyme tails of a line: one per reading of its last stressed word that the fit allows.

    Under a meter that is the chosen stress (with every ё spelling of it); in
    free verse every stress the word can take, so the best one can be matched.
    """
    words = line.words
    ss = slots(words, fit.elided)
    k = _anchor(ss)
    if k is None:
        return []
    w = ss[k].word
    word = words[w]
    chosen = fit.stresses.get(w)
    if chosen is None and ss[k].lead and w > 0:  # по́ лесу: the preposition took the stress
        prep, lean = words[w - 1], word.readings[-1]
        t = _tail(prep, prep.readings[0], 0, [])
        if t is None:
            return []
        rest = t.rest + lean.phones + tuple(p for x in words[w + 1 :] for p in x.readings[0].phones)
        shown = " ".join(x.text for x in words[w - 1 :])
        spelled = " ".join([prep.norm, lean.spelling, *(x.norm for x in words[w + 1 :])])
        return [
            Tail(t.onset, t.vowel, rest, sum(is_vowel(p) for p in rest), shown, spelled, word.lang)
        ]
    out = []
    for reading in word.readings:
        if reading.stress is None or (fit.meter != "free" and reading.stress != chosen):
            continue
        # English also rhymes on a secondary stress after the main one (sunshine / mine).
        later = [k for k in reading.secondary if k > reading.stress]
        if fit.promoted:  # the beat on the last syllable carries the rhyme: memory / free
            dropped_last = w in fit.elided and word.drop == word.size - 1
            later.append(word.size - (2 if dropped_last else 1))
        for stress in [reading.stress, *later]:
            t = _tail(word, reading, stress, words[w + 1 :])
            if t is not None and t not in out:
                out.append(t)
    return out


def _tail(word, reading, stress, after) -> Tail | None:
    phones = reading.phones
    vs = nuclei(phones)
    if stress is None or stress >= len(vs):
        return None
    at = vs[stress]
    start = vs[stress - 1] + 1 if stress > 0 else 0
    rest = list(phones[at + 1 :])
    shown = [word.text]
    spelled = [reading.spelling]
    for later in after:
        rest.extend(later.readings[0].phones)
        shown.append(later.text)
        spelled.append(later.norm)
    return Tail(
        onset=tuple(phones[start:at]),
        vowel=phones[at],
        rest=tuple(rest),
        post=sum(is_vowel(p) for p in rest),
        word=" ".join(shown),
        spelling=" ".join(spelled),
        lang=word.lang,
    )


def match(xs: list[Tail], ys: list[Tail]) -> tuple[float, Tail | None, Tail | None]:
    """The best-rhyming pair of readings."""
    best: tuple[float, Tail | None, Tail | None] = (
        0.0,
        xs[0] if xs else None,
        ys[0] if ys else None,
    )
    for x in xs:
        for y in ys:
            s = score(x, y)
            if s > best[0]:
                best = (s, x, y)
    return best


def score(a: Tail | None, b: Tail | None) -> float:
    if a is None or b is None:
        return 0.0
    if a.spelling == b.spelling:
        return 1.0
    vd = vowel_distance(a.vowel, b.vowel)
    if vd > 0.3:
        return 0.1
    s = 1.0 - vd
    if a.post != b.post:
        s -= 0.35
    s -= 0.5 * align_cost(a.rest, b.rest, vowel_weight=POST_TONIC_VOWELS)
    if not a.rest and not b.rest:
        # Russian and Armenian open rhymes want the consonant before the vowel too.
        x, y = a.onset[-1:], b.onset[-1:]
        if x != y and "en" not in (a.lang, b.lang):
            s -= 0.4 * (distance(x[0], y[0]) if x and y else 0.6)
    elif not a.rest or not b.rest:
        s -= 0.2  # open against closed: ду / сум
    return max(0.0, min(1.0, round(s, 3)))


def scheme(lines: list[list[Tail]], floor: float = THRESHOLD["near"]) -> str:
    """Rhyme letters for a stanza, e.g. "ABAB"; "-" for a line with nothing to rhyme."""
    letters: list[str] = []
    groups: list[list[int]] = []
    for i, ts in enumerate(lines):
        if not ts:
            letters.append("-")
            continue
        best, best_score = None, floor
        for g, members in enumerate(groups):
            s = max(match(ts, lines[m])[0] for m in members)
            if s >= best_score:
                best, best_score = g, s
        if best is None:
            groups.append([i])
            letters.append(_letter(len(groups) - 1))
        else:
            groups[best].append(i)
            letters.append(_letter(best))
    return "".join(letters)


def _letter(n: int) -> str:
    return chr(ord("A") + n % 26)
