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
INVERSION = 0.3  # an English line may open on a stressed syllable: "Sometime too hot"
PROMOTION = 0.3  # an English line may put its last beat two syllables after the stress
DOLNIK_PENALTY = 0.3
# English ternary verse lets a foot lose one weak syllable (that hóst with their bánners;
# and there láy the stéed): at the line's start, and once more inside it.
SUBSTITUTION = 0.2
MAX_INNER_SUBSTITUTIONS = 1
DOLNIK_SKIP = 0.6
MAX_ELIDABLE = 4


def syllable_range(words: list[Word], f: Fit) -> tuple[int, int]:
    """The fewest and the most syllables a line may be sung in: every droppable
    syllable sung (Գի-շե-րըն, 5) or as many left out as may be (նա ստացավ: 3-4)."""
    most = f.count + len(f.elided)
    fewest = most - max(len(r) for r in realizations(words))
    return fewest, most


def length(meter: str, feet: int, ending: int) -> int | None:
    """Syllables in a line of a classical meter with this many feet and this ending."""
    if meter not in CLASSICAL:
        return None
    period, phase = CLASSICAL[meter]
    return phase + period * (feet - 1) + 1 + ending


MAX_FEET = 50  # a sung line has far fewer; more is a typo that would hang a fit


def parse_meter(name: str) -> tuple[str, int | None]:
    """ "iamb4" -> ("iamb", 4); "trochee" -> ("trochee", None)."""
    text = name.strip().lower()
    base = text.rstrip("0123456789").strip()
    digits = text[len(base) :].strip()
    base = ALIASES.get(base, base)
    if base not in METERS and base != "free":
        raise ValueError(f"unknown meter {name!r}; use one of {', '.join(METERS)}, free")
    if digits and int(digits) > MAX_FEET:
        raise ValueError(f"a meter has at most {MAX_FEET} feet, got {name!r}")
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
    lang: str = ""
    lead: int = 0  # syllables at the start borrowed from a preposition (по́ лесу)
    free_end: bool = False  # see Word.free_end

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
    promoted: bool = False  # the last beat falls on an unstressed final syllable: témperàte

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
    """One slot per sung word; a preposition and a noun that may take its stress share one."""
    out = []
    pos = 0
    borrowed: int | None = None  # start of a preposition the next word's slot takes over
    for i, w in enumerate(words):
        size = w.size
        after = next((x for x in words[i + 1 :] if x.size), None)
        clash = after is not None and not after.clitic and 0 in after.stress_options()
        readings = [r for r in w.readings if clash or r.source != "clash"] or list(w.readings)
        options = tuple(dict.fromkeys(r.stress for r in readings))
        if force and i in force and force[i] in options:
            options = (force[i],)
        secondary = {k for r in readings for k in r.secondary}
        costs: dict[int | None, float] = {}
        for r in readings:
            costs[r.stress] = min(costs.get(r.stress, r.penalty), r.penalty)
        if i in elided and w.drop is not None:
            d = w.drop
            size -= 1
            options = tuple(
                o if o is None else o - (o > d) for o in options if o is None or o != d
            ) or (None,)
            secondary = {k - (k > d) for k in secondary if k != d}
            costs = {
                (s - (s > d) if s is not None else None): c for s, c in costs.items() if s != d
            }
        if size == 0:
            continue
        nxt = words[i + 1] if i + 1 < len(words) else None
        if nxt is not None and nxt.leans and size == 1 and w.clitic:
            borrowed, pos = pos, pos + 1
            continue
        start, lead = pos, 0
        if w.leans and borrowed is not None:  # None, the noun unstressed, is the preposition's
            start, lead, size = borrowed, 1, size + 1
            options = tuple(0 if o is None else o + 1 for o in options)
            secondary = {k + 1 for k in secondary}
            costs = {(0 if st is None else st + 1): c for st, c in costs.items()}
        elif w.leans:
            options = tuple(o for o in options if o is not None) or options
            costs = {st: c for st, c in costs.items() if st is not None}
        borrowed = None
        penalties = tuple((st, c) for st, c in costs.items() if c)
        out.append(
            Slot(
                i,
                start,
                size,
                options,
                w.weak,
                w.clitic,
                w.enclitic,
                frozenset(secondary),
                penalties,
                w.lang,
                lead,
                w.free_end,
            )
        )
        pos = start + size
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
        if k < s.lead and k != stress:  # the preposition, unstressed as usual
            cost += CLITIC_ON_BEAT if on else 0.0
            continue
        if k == stress:
            if not on:
                if s.weak or s.clitic:
                    cost += WEAK_WORD_OFF_BEAT
                elif s.lang == "en" and s.start == 0 and k == 0:
                    cost += INVERSION
                elif period == 3 and s.start == 0 and s.size <= _first_beat(strong, period):
                    cost += INVERSION  # У́тро ды́шит: a word wholly before the first beat
                else:
                    cost += STRESS_OFF_BEAT
                    off = True
        elif on and k not in s.secondary:
            cost += PYRRHIC[period]
    return cost, off


def _first_beat(strong, period: int) -> int:
    return next((p for p in range(period) if strong(p)), 0)


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
    words: list[Word],
    meter: str,
    elided: frozenset[int] = frozenset(),
    force: dict | None = None,
    promote: bool = False,
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
    end = ss[-1] if ss else None
    # waits for mé: a free pronoun on the last beat ends the line, not the verb before
    free_last = (
        anchor is not None
        and end is not None
        and end.free_end
        and strong(end.start)
        and ss[anchor] is not end
    )
    for k, s in enumerate(ss):
        best = None
        for st in s.options:
            cost, is_off = _slot_cost(s, st, strong, period)
            pos = s.start + (st or 0)
            end_off = False
            if k == anchor and st is not None and not strong(pos) and not free_last:
                cost += CLAUSULA
                end_off = True
            key = (cost, st is None)
            if best is None or key < best[0]:
                best = (key, st, is_off, end_off, pos)
        assert best is not None  # every slot has at least one option
        (cost, _), st, is_off, end_off, pos = best
        total += cost
        choice[s.word] = st
        if is_off:
            off.append(s.word)
        if k == anchor:
            ending_off = end_off
            last_pos = pos
    stressed = _stressed_grid(ss, choice, strong, count)
    main = choice[ss[anchor].word] if anchor is not None else None
    if anchor is not None and main is not None:
        s = ss[anchor]  # a secondary stress on a beat after the main one ends the line: bútterflỳ
        later = [s.start + k for k in s.secondary if k > main and strong(s.start + k)]
        last_pos = max([last_pos, *later])
    if free_last and end is not None:
        last_pos = max(last_pos, end.start)  # back to mé: the pronoun takes the last beat
    promoted = False
    if promote and anchor == len(ss) - 1 and not ending_off:
        s = ss[anchor]
        st = choice[s.word]
        if s.lang == "en" and st is not None and s.size - st == 3 and strong(count - 1):
            promoted, last_pos = True, count - 1
            total += PROMOTION
            stressed = stressed[:-1] + (True,)
    feet = (last_pos - phase) // period + 1 if last_pos >= phase else 0
    return Fit(
        meter=meter,
        cost=round(total, 3),
        feet=feet,
        count=count,
        elided=elided,
        stresses=_own(choice, words, elided, ss),
        beats=tuple(strong(p) for p in range(count)),
        stressed=stressed,
        off_beat=off,
        ending_off=ending_off,
        promoted=promoted,
    )


def fit_dolnik(
    words: list[Word],
    elided: frozenset[int] = frozenset(),
    force: dict | None = None,
    feet: int | None = None,
) -> Fit:
    """Best dolnik fit; with feet, the best one with that many ictuses if any exists."""
    ss = slots(words, elided, force)
    count = sum(s.size for s in ss)
    ambiguous = [s for s in ss if len(s.options) > 1][:5]
    best: Fit | None = None

    def key(f: Fit) -> tuple:
        return (feet is not None and f.feet != feet, f.cost)

    for combo in product(*(s.options for s in ambiguous)):
        picked = {s.word: st for s, st in zip(ambiguous, combo)}
        choice = {s.word: picked.get(s.word, s.options[0]) for s in ss}
        fit = _dolnik_one(words, ss, choice, count, elided, feet)
        if fit is not None and (best is None or key(fit) < key(best)):
            best = fit
    if best is None:
        choice = {s.word: s.options[0] for s in ss}
        grid = _stressed_grid(ss, choice, None, count)
        return Fit(
            "dolnik",
            99.0,
            0,
            count,
            elided,
            _own(choice, words, elided, ss),
            (False,) * count,
            grid,
        )
    return best


def _kinds(ss: list[Slot], choice: dict, count: int) -> list[str]:
    """S stressed polysyllable, W stressed function word, m monosyllable, c clitic,
    u unstressed, for each sung syllable."""
    kind = ["u"] * count
    for s in ss:
        st = choice[s.word]
        if s.size == 1:
            kind[s.start] = "c" if (s.clitic or st is None) else "m"
        elif st is not None:
            for k in range(s.lead):
                kind[s.start + k] = "c"
            kind[s.start + st] = "m" if st < s.lead else ("W" if (s.weak or s.clitic) else "S")
    return kind


def fit_loose(
    words: list[Word],
    meter: str,
    elided: frozenset[int] = frozenset(),
    force: dict | None = None,
    feet: int | None = None,
) -> Fit | None:
    """English ternary verse with its usual substitutions: a foot one weak syllable
    short at the start of the line, and once inside it."""
    period, phase = CLASSICAL[meter]
    ss = slots(words, elided, force)
    count = sum(s.size for s in ss)
    ambiguous = [s for s in ss if len(s.options) > 1][:5]
    best: Fit | None = None
    for combo in product(*(s.options for s in ambiguous)):
        picked = {s.word: st for s, st in zip(ambiguous, combo)}
        choice = {s.word: picked.get(s.word, s.options[0]) for s in ss}
        f = _loose_one(words, ss, choice, count, elided, meter, period, phase, feet)
        if f is not None and (
            best is None or (f.feet != feet, f.cost) < (best.feet != feet, best.cost)
        ):
            best = f
    return best


def _loose_one(words, ss, choice, count, elided, meter, period, phase, feet) -> Fit | None:
    kind = _kinds(ss, choice, count)
    anchor = _anchor(ss)
    if anchor is None:
        return None
    a = ss[anchor]
    st = choice[a.word]
    last = a.start + (st or 0)
    best = _loose_beats(kind, count, last, period, phase, feet)
    end = ss[-1]
    if end.free_end and end is not a:
        # waits for mé: the pronoun may take the last beat instead
        on_end = list(kind)
        on_end[end.start] = "m"
        alt = _loose_beats(on_end, count, end.start, period, phase, feet)
        if alt is not None and (best is None or _loose_key(alt, feet) < _loose_key(best, feet)):
            best, last, kind = alt, end.start, on_end
    promoted = False
    final = a.size - 1
    if (
        a.lang == "en"
        and st is not None
        and anchor == len(ss) - 1
        and final in a.secondary
        and final - st >= 2
    ):
        # deep Gal-i-lée: the last beat on a final secondary, the main stress yielding
        yielded = list(kind)
        yielded[a.start + st] = "W"
        alt = _loose_beats(yielded, count, a.start + final, period, phase, feet)
        if alt is not None:
            alt = (alt[0] + PROMOTION, *alt[1:])
            if best is None or _loose_key(alt, feet) < _loose_key(best, feet):
                best, promoted, last, kind = alt, True, a.start + final, yielded
    if best is None:
        return None
    cost, n, beats = best
    off_words = [
        s.word
        for s in ss
        if s.size > 1
        and choice[s.word] is not None
        and not beats[s.start + choice[s.word]]
        and not (s.weak or s.clitic)
        and not (promoted and s is a)
    ]
    tail = sum(_off(kind[t]) for t in range(last + 1, count))
    return Fit(
        meter=meter,
        cost=round(cost + tail + sum(s.penalty(choice[s.word]) for s in ss), 3),
        feet=n,
        count=count,
        elided=elided,
        stresses=_own(choice, words, elided, ss),
        beats=tuple(beats),
        stressed=_stressed_grid(ss, choice, lambda p: beats[p], count),
        off_beat=off_words,
        promoted=promoted,
    )


def _off(kind: str) -> float:
    return {"S": STRESS_OFF_BEAT, "W": WEAK_WORD_OFF_BEAT, "m": MONO_OFF_BEAT}.get(kind, 0.0)


def _loose_key(fit: tuple[float, int, list[bool]], feet: int | None) -> tuple:
    return (feet is not None and fit[1] != feet, fit[0])


def _loose_beats(kind, count, last, period, phase, feet) -> tuple[float, int, list[bool]] | None:
    """The cheapest beats ending on last: (cost, number of beats, beat per syllable)."""

    def on(i: int) -> float:
        return {"u": PYRRHIC[period], "c": CLITIC_ON_BEAT}.get(kind[i], 0.0)

    # dp[i][(n, subs)]: cheapest beats ending on i, with n beats and subs short feet inside
    dp: list[dict[tuple[int, int], tuple[float, int]]] = [{} for _ in range(count)]
    for i, extra in ((phase, 0.0), (phase - 1, SUBSTITUTION)):
        if 0 <= i <= last:
            dp[i][(1, 0)] = (on(i) + extra + sum(_off(kind[j]) for j in range(i)), -1)
    for i in range(1, last + 1):
        for gap, extra in ((period, 0.0), (period - 1, SUBSTITUTION)):
            j = i - gap
            if j < 0:
                continue
            for (n, subs), (c0, _) in dp[j].items():
                subs2 = subs + (gap < period)
                if subs2 > MAX_INNER_SUBSTITUTIONS:
                    continue
                c = c0 + extra + on(i) + sum(_off(kind[t]) for t in range(j + 1, i))
                k = (n + 1, subs2)
                if k not in dp[i] or c < dp[i][k][0]:
                    dp[i][k] = (c, j)
    ends = dp[last]
    if not ends:
        return None
    key = min(ends, key=lambda k: (feet is not None and k[0] != feet, ends[k][0]))
    beats = [False] * count
    i, state = last, key
    while i >= 0:
        beats[i] = True
        j = dp[i][state][1]
        state = (state[0] - 1, state[1] - (j >= 0 and i - j < period))
        i = j
    return ends[key][0], key[0], beats


def _dolnik_one(words, ss, choice, count, elided, feet: int | None = None) -> Fit | None:
    kind = _kinds(ss, choice, count)
    anchor = _anchor(ss)
    if anchor is None:
        return None
    a = ss[anchor]
    last = a.start + (choice[a.word] or 0)

    def on(i: int) -> float:
        return {"u": DOLNIK_SKIP, "c": CLITIC_ON_BEAT}.get(kind[i], 0.0)

    def off(i: int) -> float:
        return {"S": STRESS_OFF_BEAT, "W": WEAK_WORD_OFF_BEAT, "m": MONO_OFF_BEAT}.get(kind[i], 0.0)

    ends = [0] * count  # where the word of each syllable ends
    for s in ss:
        for k in range(s.start, s.start + s.size):
            ends[k] = s.start + s.size

    def lead_in(i: int) -> float:
        """The syllables before a first beat on i: a word wholly among them may keep
        its stress (Сму́глый о́трок бродил по аллеям)."""
        return sum(INVERSION if kind[j] == "S" and ends[j] <= i else off(j) for j in range(i))

    # dp[i][n]: cheapest beats ending on syllable i with n ictuses, and the beat before
    dp: list[dict[int, tuple[float, int]]] = [{} for _ in range(count)]
    for i in range(min(3, last + 1)):
        dp[i][1] = (on(i) + lead_in(i), -1)
    for i in range(2, last + 1):
        for gap in (2, 3):
            j = i - gap
            if j < 0:
                continue
            for n, (c0, _) in dp[j].items():
                c = c0 + on(i) + sum(off(t) for t in range(j + 1, i))
                if n + 1 not in dp[i] or c < dp[i][n + 1][0]:
                    dp[i][n + 1] = (c, j)
    ends = dp[last]
    if not ends:
        return None
    n = feet if feet is not None and feet in ends else min(ends, key=lambda k: ends[k][0])
    cost = ends[n][0]
    beats = [False] * count
    i, ictuses = last, n
    while i >= 0:
        beats[i] = True
        i = dp[i][ictuses][1]
        ictuses -= 1
    tail = sum(off(t) for t in range(last + 1, count))
    first = beats.index(True)
    off_words = [
        s.word
        for s in ss
        if s.size > 1
        and choice[s.word] is not None
        and not beats[s.start + choice[s.word]]
        and not (s.weak or s.clitic)
        and s.start + s.size > first
    ]
    return Fit(
        meter="dolnik",
        cost=round(cost + tail + DOLNIK_PENALTY + sum(s.penalty(choice[s.word]) for s in ss), 3),
        feet=n,
        count=count,
        elided=elided,
        stresses=_own(choice, words, elided, ss),
        beats=tuple(beats),
        stressed=_stressed_grid(ss, choice, lambda p: beats[p], count),
        off_beat=off_words,
    )


def _own(
    choice: dict[int, int | None], words: list[Word], elided: frozenset[int], ss: list[Slot]
) -> dict:
    """Stress indices back in each word's own syllables, undoing dropped schwas and the
    syllable a noun borrowed from its preposition (None when the preposition took it)."""
    out = {}
    choice = dict(choice)
    for s in ss:
        if s.lead and s.word in choice:
            st = choice[s.word]
            choice[s.word] = None if st is None or st < s.lead else st - s.lead
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
    feet: int | None = None,
    promote: bool | None = None,
) -> Fit:
    """Best fit of words to meter, preferring realizations whose length matches count,
    then those with the asked number of feet. English lines also try a promoted last
    beat (promote=None), or only that (promote=True). When the feet are missed, each
    ambiguous word's other readings are tried too: four feet of trochee make
    облака́, not о́блака."""
    key, best = _fit(words, meter, count, tolerance, force, feet, promote)
    if feet is None or best.feet == feet or meter == "free":
        return best
    for i, w in enumerate(words):
        options = w.stress_options()
        if (force and i in force) or len(options) < 2:
            continue
        for option in options:
            if option == best.stresses.get(i):
                continue
            k, f = _fit(words, meter, count, tolerance, {**(force or {}), i: option}, feet, promote)
            if k < key:
                key, best = k, f
    return best


def _fit(words, meter, count, tolerance, force, feet, promote) -> tuple[tuple, Fit]:
    scored = []
    english = any(w.lang == "en" for w in words)
    for elided in realizations(words):
        if meter == "dolnik":
            fits = [fit_dolnik(words, elided, force, feet)]
        elif meter == "free":
            fits = [free_fit(words, elided, force)]
        else:
            fits = [] if promote and english else [fit_classical(words, meter, elided, force)]
            if english and promote is not False:
                fits.append(fit_classical(words, meter, elided, force, promote=True))
            if english and not promote and CLASSICAL[meter][0] == 3:
                loose = fit_loose(words, meter, elided, force, feet)
                if loose is not None:
                    fits.append(loose)
        for f in fits:
            miss = 0 if count is None else max(0, abs(f.count - count) - tolerance)
            off_feet = feet is not None and f.feet != feet
            licence = sum(words[i].drop_cost for i in elided)
            scored.append(((miss, off_feet, f.cost + licence, len(elided)), f))
    return min(scored, key=lambda kf: kf[0])


def free_fit(
    words: list[Word], elided: frozenset[int] = frozenset(), force: dict | None = None
) -> Fit:
    ss = slots(words, elided, force)
    count = sum(s.size for s in ss)
    choice = {s.word: s.options[0] for s in ss}
    stressed = _stressed_grid(ss, choice, None, count)
    return Fit(
        "free",
        0.0,
        sum(stressed),
        count,
        elided,
        _own(choice, words, elided, ss),
        stressed,
        stressed,
    )


MAX_SUNG_LINE = 64  # syllables; past this no meter is looked for (the fit grows quadratically)


def detect(lines: list[Line]) -> str:
    """The meter that fits a stanza best, or "free" if none fits well."""
    usable = [ln for ln in lines if ln.words]
    if not usable or any(sum(w.size for w in ln.words) > MAX_SUNG_LINE for ln in usable):
        return "free"
    totals = {}
    for m in METERS:
        totals[m] = sum(fit(ln.words, m).cost for ln in usable)
    best = min(METERS, key=lambda m: (totals[m], METERS.index(m)))
    if totals[best] / len(usable) > 1.0:
        return "free"
    return best
