"""Fitting a line's stresses to a meter.

A meter marks every syllable position as a strong or a weak beat. Fitting a
line means choosing, for each word whose stress is ambiguous or unknown, the
reading that suits the beats best, and pricing what does not fit:

* the stress of a polysyllable on a weak beat is a real fault (1.0);
* an unstressed syllable on a strong beat is a pyrrhic, normal in binary meters
  and rarer in ternary ones (0.1 / 0.4);
* monosyllables and function words may take either beat at a small cost;
* the last stress of the line must land on a strong beat (1.5).

Syllables after the last stress are the ending (masculine 0, feminine 1,
dactylic 2) and are not counted as beats. Armenian prothetic schwas that can
merge into a preceding vowel give a line more than one realization; the fit
tries each.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations, product

from .model import Line, Word

CLASSICAL = {
    "iamb": (2, 1),
    "trochee": (2, 0),
    "dactyl": (3, 0),
    "amphibrach": (3, 1),
    "anapest": (3, 2),
}
METERS = (*CLASSICAL, "dolnik")
ALIASES = {
    "iambic": "iamb",
    "trochaic": "trochee",
    "dactylic": "dactyl",
    "amphibrachic": "amphibrach",
    "anapaest": "anapest",
    "anapestic": "anapest",
    "ямб": "iamb",
    "хорей": "trochee",
    "дактиль": "dactyl",
    "амфибрахий": "amphibrach",
    "анапест": "anapest",
    "дольник": "dolnik",
}

STRESS_OFF_BEAT = 1.0
WEAK_WORD_OFF_BEAT = 0.3
PYRRHIC = {2: 0.1, 3: 0.4}
MONO_OFF_BEAT = 0.1
CLITIC_ON_BEAT = 0.1
CLAUSULA = 1.5
DOLNIK_PENALTY = 0.3
DOLNIK_SKIP = 0.6
MAX_ELIDABLE = 4


def length(meter: str, feet: int, ending: int) -> int | None:
    """Syllables in a line of a classical meter with this many feet and this ending."""
    if meter not in CLASSICAL:
        return None
    period, phase = CLASSICAL[meter]
    return phase + period * (feet - 1) + 1 + ending


def parse_meter(name: str) -> tuple[str, int | None]:
    """ "iamb4" -> ("iamb", 4); "trochee" -> ("trochee", None)."""
    text = name.strip().lower()
    digits = "".join(ch for ch in text if ch.isdigit())
    base = text.rstrip("0123456789").strip()
    base = ALIASES.get(base, base)
    if base not in METERS and base != "free":
        raise ValueError(f"unknown meter {name!r}; use one of {', '.join(METERS)}, free")
    return base, int(digits) if digits else None


@dataclass(frozen=True)
class Slot:
    word: int
    start: int
    size: int
    options: tuple[int | None, ...]
    weak: bool
    clitic: bool
    enclitic: bool
    secondary: frozenset[int] = frozenset()  # may take a beat or skip it for free
    penalties: tuple[tuple[int | None, float], ...] = ()  # extra cost of a stress option

    def penalty(self, stress: int | None) -> float:
        return next((c for s, c in self.penalties if s == stress), 0.0)


@dataclass
class Fit:
    meter: str
    cost: float
    feet: int
    count: int
    elided: frozenset[int]
    stresses: dict[int, int | None]  # word index -> chosen stress, in the word's own syllables
    beats: tuple[bool, ...]  # per sung syllable: strong beat?
    stressed: tuple[bool, ...]  # per sung syllable: carries the stress?
    off_beat: list[int] = field(default_factory=list)  # words whose stress hits a weak beat
    ending_off: bool = False  # the line's last stress hits a weak beat

    @property
    def grid(self) -> str:
        return "".join("/" if s else "x" for s in self.stressed)

    @property
    def template(self) -> str:
        """The beats the meter asks for over the whole line."""
        return "".join("/" if b else "x" for b in self.beats)

    @property
    def ending(self) -> int:
        """Syllables after the last stress."""
        for i in range(len(self.stressed) - 1, -1, -1):
            if self.stressed[i]:
                return len(self.stressed) - 1 - i
        return 0


def slots(words: list[Word], elided: frozenset[int], force: dict | None = None) -> list[Slot]:
    out = []
    pos = 0
    for i, w in enumerate(words):
        size = w.size
        options = tuple(w.stress_options())
        if force and i in force and force[i] in options:
            options = (force[i],)
        secondary = {k for r in w.readings for k in r.secondary}
        costs: dict[int | None, float] = {}
        for r in w.readings:
            costs[r.stress] = min(costs.get(r.stress, r.penalty), r.penalty)
        if i in elided and w.drop is not None:
            d = w.drop
            size -= 1
            options = tuple(o - (o > d) for o in options if o is None or o != d) or (None,)
            secondary = {k - (k > d) for k in secondary if k != d}
            costs = {
                (s - (s > d) if s is not None else None): c for s, c in costs.items() if s != d
            }
        if size == 0:
            continue
        penalties = tuple((s, c) for s, c in costs.items() if c)
        out.append(
            Slot(
                i, pos, size, options, w.weak, w.clitic, w.enclitic, frozenset(secondary), penalties
            )
        )
        pos += size
    return out


def realizations(words: list[Word]) -> list[frozenset[int]]:
    """Sets of words whose droppable schwa is dropped, the empty set first."""
    droppable = [i for i, w in enumerate(words) if w.drop is not None][:MAX_ELIDABLE]
    out = [frozenset()]
    for k in range(1, len(droppable) + 1):
        out.extend(frozenset(c) for c in combinations(droppable, k))
    return out


def _anchor(ss: list[Slot]) -> int | None:
    """Index in ss of the word carrying the line's last stress."""
    for k in range(len(ss) - 1, -1, -1):
        s = ss[k]
        if s.clitic or s.enclitic or s.options == (None,):
            continue
        return k
    return None


def _slot_cost(s: Slot, stress: int | None, strong, period: int) -> tuple[float, bool]:
    cost, off = _beat_cost(s, stress, strong, period)
    return cost + s.penalty(stress), off


def _beat_cost(s: Slot, stress: int | None, strong, period: int) -> tuple[float, bool]:
    if s.size == 1 and stress in (0, None):
        on = strong(s.start)
        if s.clitic or stress is None:
            return (CLITIC_ON_BEAT if on else 0.0), False
        return (0.0 if on else MONO_OFF_BEAT), False
    cost, off = 0.0, False
    for k in range(s.size):
        on = strong(s.start + k)
        if k == stress:
            if not on:
                if s.weak or s.clitic:
                    cost += WEAK_WORD_OFF_BEAT
                else:
                    cost += STRESS_OFF_BEAT
                    off = True
        elif on and k not in s.secondary:
            cost += PYRRHIC[period]
    return cost, off


def _stressed_grid(ss: list[Slot], choice: dict[int, int | None], strong, count: int) -> tuple:
    """Which syllables carry stress; a monosyllable does when it takes a beat or ends the line."""
    a = _anchor(ss)
    last_word = ss[a].word if a is not None else None
    grid = [False] * count
    for s in ss:
        st = choice[s.word]
        if st is None:
            continue
        if s.size == 1:
            on = strong is None or strong(s.start)
            grid[s.start] = s.word == last_word or (not s.clitic and on)
        else:
            grid[s.start + st] = True
            for k in s.secondary:
                if strong is not None and strong(s.start + k):
                    grid[s.start + k] = True
    return tuple(grid)


def fit_classical(
    words: list[Word], meter: str, elided: frozenset[int] = frozenset(), force: dict | None = None
) -> Fit:
    period, phase = CLASSICAL[meter]

    def strong(p: int) -> bool:
        return p % period == phase

    ss = slots(words, elided, force)
    count = sum(s.size for s in ss)
    anchor = _anchor(ss)
    total = 0.0
    choice: dict[int, int | None] = {}
    off: list[int] = []
    ending_off = False
    last_pos = count - 1
    for k, s in enumerate(ss):
        best = None
        for st in s.options:
            cost, is_off = _slot_cost(s, st, strong, period)
            pos = s.start + (st or 0)
            end_off = False
            if k == anchor and st is not None and not strong(pos):
                cost += CLAUSULA
                end_off = True
            key = (cost, st is None)
            if best is None or key < best[0]:
                best = (key, st, is_off, end_off, pos)
        (cost, _), st, is_off, end_off, pos = best
        total += cost
        choice[s.word] = st
        if is_off:
            off.append(s.word)
        if k == anchor:
            ending_off = end_off
            last_pos = pos
    feet = (last_pos - phase) // period + 1 if last_pos >= phase else 0
    return Fit(
        meter=meter,
        cost=round(total, 3),
        feet=feet,
        count=count,
        elided=elided,
        stresses=_own(choice, words, elided),
        beats=tuple(strong(p) for p in range(count)),
        stressed=_stressed_grid(ss, choice, strong, count),
        off_beat=off,
        ending_off=ending_off,
    )


def fit_dolnik(
    words: list[Word], elided: frozenset[int] = frozenset(), force: dict | None = None
) -> Fit:
    ss = slots(words, elided, force)
    count = sum(s.size for s in ss)
    ambiguous = [s for s in ss if len(s.options) > 1][:5]
    best: Fit | None = None
    for combo in product(*(s.options for s in ambiguous)):
        picked = {s.word: st for s, st in zip(ambiguous, combo)}
        choice = {s.word: picked.get(s.word, s.options[0]) for s in ss}
        fit = _dolnik_one(words, ss, choice, count, elided)
        if fit is not None and (best is None or fit.cost < best.cost):
            best = fit
    if best is None:
        choice = {s.word: s.options[0] for s in ss}
        grid = _stressed_grid(ss, choice, None, count)
        return Fit(
            "dolnik", 99.0, 0, count, elided, _own(choice, words, elided), (False,) * count, grid
        )
    return best


def _dolnik_one(words, ss, choice, count, elided) -> Fit | None:
    # S stressed polysyllable, W stressed function word, m monosyllable, c clitic, u unstressed
    kind = ["u"] * count
    for s in ss:
        st = choice[s.word]
        if s.size == 1:
            kind[s.start] = "c" if (s.clitic or st is None) else "m"
        elif st is not None:
            kind[s.start + st] = "W" if (s.weak or s.clitic) else "S"
    anchor = _anchor(ss)
    if anchor is None:
        return None
    a = ss[anchor]
    last = a.start + (choice[a.word] or 0)

    def on(i: int) -> float:
        return {"u": DOLNIK_SKIP, "c": CLITIC_ON_BEAT}.get(kind[i], 0.0)

    def off(i: int) -> float:
        return {"S": STRESS_OFF_BEAT, "W": WEAK_WORD_OFF_BEAT, "m": MONO_OFF_BEAT}.get(kind[i], 0.0)

    inf = float("inf")
    dp = [inf] * count
    back = [-1] * count
    for i in range(min(3, last + 1)):
        dp[i] = on(i) + sum(off(j) for j in range(i))
    for i in range(2, last + 1):
        for gap in (2, 3):
            j = i - gap
            if j < 0 or dp[j] == inf:
                continue
            c = dp[j] + on(i) + sum(off(t) for t in range(j + 1, i))
            if c < dp[i]:
                dp[i], back[i] = c, j
    if dp[last] == inf:
        return None
    beats = [False] * count
    i, feet = last, 0
    while i >= 0:
        beats[i] = True
        feet += 1
        i = back[i]
    tail = sum(off(t) for t in range(last + 1, count))
    off_words = [
        s.word
        for s in ss
        if s.size > 1
        and choice[s.word] is not None
        and not beats[s.start + choice[s.word]]
        and not (s.weak or s.clitic)
    ]
    return Fit(
        meter="dolnik",
        cost=round(
            dp[last] + tail + DOLNIK_PENALTY + sum(s.penalty(choice[s.word]) for s in ss), 3
        ),
        feet=feet,
        count=count,
        elided=elided,
        stresses=_own(choice, words, elided),
        beats=tuple(beats),
        stressed=_stressed_grid(ss, choice, lambda p: beats[p], count),
        off_beat=off_words,
    )


def _own(choice: dict[int, int | None], words: list[Word], elided: frozenset[int]) -> dict:
    """Stress indices back in each word's own syllables, undoing dropped schwas."""
    out = {}
    for w, st in choice.items():
        d = words[w].drop
        out[w] = st + 1 if w in elided and st is not None and d is not None and st >= d else st
    return out


def fit(
    words: list[Word],
    meter: str,
    count: int | None = None,
    tolerance: int = 0,
    force: dict[int, int | None] | None = None,
) -> Fit:
    """Best fit of words to meter, preferring realizations whose length matches count."""
    scored = []
    for elided in realizations(words):
        if meter == "dolnik":
            f = fit_dolnik(words, elided, force)
        elif meter == "free":
            f = free_fit(words, elided, force)
        else:
            f = fit_classical(words, meter, elided, force)
        miss = 0 if count is None else max(0, abs(f.count - count) - tolerance)
        scored.append(((miss, f.cost, len(elided)), f))
    return min(scored, key=lambda kf: kf[0])[1]


def free_fit(
    words: list[Word], elided: frozenset[int] = frozenset(), force: dict | None = None
) -> Fit:
    ss = slots(words, elided, force)
    count = sum(s.size for s in ss)
    choice = {s.word: s.options[0] for s in ss}
    stressed = _stressed_grid(ss, choice, None, count)
    return Fit(
        "free", 0.0, sum(stressed), count, elided, _own(choice, words, elided), stressed, stressed
    )


def detect(lines: list[Line]) -> str:
    """The meter that fits a stanza best, or "free" if none fits well."""
    usable = [ln for ln in lines if ln.words]
    if not usable:
        return "free"
    totals = {}
    for m in METERS:
        totals[m] = sum(fit(ln.words, m).cost for ln in usable)
    best = min(METERS, key=lambda m: (totals[m], METERS.index(m)))
    if totals[best] / len(usable) > 1.0:
        return "free"
    return best
