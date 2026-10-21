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

from dataclasses import dataclass, replace

from .lang.en import OBJECTS, PREPOSITIONS
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

    @property
    def rime(self) -> str:
        """What a partner must sound like: the stressed vowel and what follows,
        with the consonant before it where Russian and Armenian open rhymes want
        it (ты / красоты)."""
        if not self.rest and self.lang in ("ru", "hy"):
            return self.sound
        return self.vowel + "".join(self.rest)


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


def tails(line: Line, fit: Fit, chosen_only: bool = False) -> list[Tail]:
    """Rhyme tails of a line: one per reading of its last stressed word that the fit allows.

    Under a meter that is the chosen stress (with every ё spelling of it); in
    free verse every stress the word can take, so the best one can be matched,
    unless chosen_only asks for the fit's own reading there too.
    """
    words = line.words
    ss = slots(words, fit.elided)
    k = _anchor(ss)
    if k is None:
        return []
    w = ss[k].word
    word = words[w]
    chosen = fit.stresses.get(w)
    shifted = _shifted_tail(words, w) if ss[k].lead and w > 0 else None
    if chosen is None and shifted is not None:  # по́ лесу: the preposition took the stress
        return [shifted]
    free = fit.meter == "free" and not chosen_only
    out = [shifted] if free and shifted is not None else []
    for reading in word.readings:
        if reading.stress is None or (not free and reading.stress != chosen):
            continue
        if reading.source == "clash" and reading.stress != chosen:
            continue  # no stressed word follows the rhyme to clash with
        # English also rhymes on a secondary stress after the main one (sunshine / mine).
        later = [k for k in reading.secondary if k > reading.stress]
        if fit.promoted:  # the beat on the last syllable carries the rhyme: memory / free
            dropped_last = w in fit.elided and word.drop == word.size - 1
            later.append(word.size - (2 if dropped_last else 1))
        # Sung short (real in one syllable rhymes with feel), and as written (fire
        # in one syllable still rhymes with empire).
        sung = _as_sung(word, reading, w in fit.elided)
        for stress in [reading.stress, *later]:
            for form in dict.fromkeys([sung, reading]):
                t = _tail(word, form, stress, words[w + 1 :])
                if t is not None and t not in out:
                    out.append(t)
    last = words[-1]
    leaning = w == len(words) - 3 and words[-2].norm in PREPOSITIONS
    if (w == len(words) - 2 or leaning) and last.lang == "en" and last.enclitic:
        own = _tail(last, last.readings[0], 0, [])  # love yóu / true, walk with mé / free
        if own is not None and own not in out:
            out.append(own)
    return out


def _as_sung(word, reading, elided: bool):
    """The reading as the line sings it: real in one syllable rhymes with feel."""
    if not elided or word.drop is None or reading.stress is None or word.drop <= reading.stress:
        return reading
    vs = nuclei(reading.phones)
    if word.drop >= len(vs):
        return reading
    cut = vs[word.drop]
    return replace(reading, phones=reading.phones[:cut] + reading.phones[cut + 1 :])


def _shifted_tail(words, w: int) -> Tail | None:
    """The tail of a line whose word w gives its stress to the preposition before it."""
    prep, word = words[w - 1], words[w]
    lean = word.readings[-1]
    t = _tail(prep, prep.readings[0], 0, [])
    if t is None:
        return None
    rest = t.rest + lean.phones + tuple(p for x in words[w + 1 :] for p in x.readings[0].phones)
    shown = " ".join(x.text for x in words[w - 1 :])
    spelled = " ".join([prep.norm, lean.spelling, *(x.norm for x in words[w + 1 :])])
    return Tail(t.onset, t.vowel, rest, sum(is_vowel(p) for p in rest), shown, spelled, word.lang)


def _tail(word, reading, stress, after) -> Tail | None:
    phones = reading.phones
    vs = nuclei(phones)
    if stress is None or stress >= len(vs):
        return None
    at = vs[stress]
    start = vs[stress - 1] + 1 if stress > 0 else 0
    rest = list(phones[at + 1 :])
    if word.lang == "en" and phones[at] in ("aɪ", "aʊ") and rest[:1] == ["ɚ"]:
        rest[0] = "ɹ"  # fire AY1 ER0 rhymes with retire AY1 R, hour with sour
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
    if a.spelling == b.spelling and (a.vowel, a.rest) == (b.vowel, b.rest):
        # The same object pronoun on both lines is no rhyme: need it / want it rhymes
        # on need and want, or not at all. A homograph stressed apart (за́мок, замо́к)
        # is compared by sound below.
        return 0.0 if a.lang == "en" and a.spelling in OBJECTS else 1.0
    merged = _english_merger(a, b)
    vd = 0.0 if merged else vowel_distance(a.vowel, b.vowel)
    if vd > 0.3 or (not merged and _english_contrast(a, b)):
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


def _english_merger(a: Tail, b: Tail) -> bool:
    """Vowels English does not tell apart before r, however CMUdict writes them:
    here / year (NEAR) and tour / poor (CURE)."""
    pair = {a.vowel, b.vowel}
    return (
        "en" in (a.lang, b.lang)
        and pair in ({"i", "ɪ"}, {"u", "ʊ"})
        and a.rest[:1] == b.rest[:1] == ("ɹ",)
    )


def _english_contrast(a: Tail, b: Tail) -> bool:
    """Stressed vowels English keeps apart though they sound close: still / feel (KIT
    and FLEECE), and far / war (START and NORTH) before r, where no accent merges them
    as cot and caught merge."""
    if "en" not in (a.lang, b.lang):
        return False
    pair = {a.vowel, b.vowel}
    return pair == {"i", "ɪ"} or (pair == {"ɑ", "ɔ"} and a.rest[:1] == b.rest[:1] == ("ɹ",))


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
