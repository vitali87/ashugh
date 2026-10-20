"""English: syllables, primary and secondary stress, and phonemes from CMUdict.

Pronunciations come from the bundled CMU Pronouncing Dictionary table
(src/ashugh/data/en_cmudict.tsv). When CMUdict lists a variant with one vowel
fewer (every: ev-e-ry / ev-ry, fire: fi-er / fire), the word gets a droppable
syllable, and the meter keeps whichever length fits the slot. Words missing
from the dictionary get a spelling-based syllable count and every stress as
a candidate, and the report warns about them.
"""

from __future__ import annotations

import re
import unicodedata

from ..model import Reading, Syllable, Word
from ..table import SortedTable, SuffixPrior

CODE = "en"
NAME = "English"

TABLE = SortedTable("data/en_cmudict.tsv")
SUFFIXES = SuffixPrior("data/en_suffix.tsv")

VOWELS_ARPA = {
    "AA": "ɑ",
    "AE": "æ",
    "AH": "ʌ",
    "AO": "ɔ",
    "AW": "aʊ",
    "AY": "aɪ",
    "EH": "ɛ",
    "ER": "ɝ",
    "EY": "eɪ",
    "IH": "ɪ",
    "IY": "i",
    "OW": "oʊ",
    "OY": "ɔɪ",
    "UH": "ʊ",
    "UW": "u",
}
UNSTRESSED_ARPA = {"AH": "ə", "ER": "ɚ"}
CONSONANTS_ARPA = {
    "P": "p",
    "B": "b",
    "T": "t",
    "D": "d",
    "K": "k",
    "G": "g",
    "CH": "tʃ",
    "JH": "dʒ",
    "F": "f",
    "V": "v",
    "TH": "θ",
    "DH": "ð",
    "S": "s",
    "Z": "z",
    "SH": "ʃ",
    "ZH": "ʒ",
    "HH": "h",
    "M": "m",
    "N": "n",
    "NG": "ŋ",
    "L": "l",
    "R": "ɹ",
    "W": "w",
    "Y": "j",
}

# Unstressed in verse and never the rhyme word: articles, short prepositions
# and conjunctions. Pronouns and auxiliaries are only metrically free (weak),
# because a line can end on them ("for me", "you are").
CLITICS = {
    "a",
    "an",
    "the",
    "of",
    "to",
    "in",
    "on",
    "at",
    "by",
    "for",
    "from",
    "with",
    "and",
    "or",
    "but",
    "nor",
    "as",
    "if",
    "than",
    "o'er",
}
WEAK = {
    "into",
    "onto",
    "upon",
    "unto",
    "about",
    "over",
    "under",
    "after",
    "before",
    "between",
    "without",
    "within",
    "because",
    "although",
    "unless",
    "until",
}

STRESS_SHIFT = 0.3  # meter cost of a compound's stress moving onto its secondary stress
LETTER_VOWELS = "aeiouy"
LETTER_PHONES = {
    "a": "æ",
    "e": "ɛ",
    "i": "ɪ",
    "o": "ɑ",
    "u": "ʌ",
    "y": "i",
    "b": "b",
    "c": "k",
    "d": "d",
    "f": "f",
    "g": "g",
    "h": "h",
    "j": "dʒ",
    "k": "k",
    "l": "l",
    "m": "m",
    "n": "n",
    "p": "p",
    "q": "k",
    "r": "ɹ",
    "s": "s",
    "t": "t",
    "v": "v",
    "w": "w",
    "x": "s",
    "z": "z",
}


def is_latin(ch: str) -> bool:
    return ch.isascii() and ch.isalpha() or "À" <= ch <= "ɏ"


def normalize(token: str) -> str:
    """Lowercase, plain letters (café -> cafe, naïve -> naive), straight apostrophes."""
    decomposed = unicodedata.normalize("NFD", token.lower().replace("’", "'"))
    norm = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    if norm.endswith("in'"):
        return norm.lstrip("'")  # goin': CMUdict lists it, and lookup tries going
    return norm.strip("'")


def _parse(variant: str) -> tuple[tuple[str, ...], list[int], list[str]]:
    """Phonemes, stress digit per vowel, and bare vowel symbols of one ARPABET string."""
    phones: list[str] = []
    stresses: list[int] = []
    bare: list[str] = []
    for symbol in variant.split():
        head = symbol.rstrip("012")
        if head in VOWELS_ARPA:
            digit = int(symbol[len(head) :] or 0)
            phones.append(
                UNSTRESSED_ARPA.get(head, VOWELS_ARPA[head]) if digit == 0 else VOWELS_ARPA[head]
            )
            stresses.append(digit)
            bare.append(head)
        elif head in CONSONANTS_ARPA:
            phones.append(CONSONANTS_ARPA[head])
    return tuple(phones), stresses, bare


def override_error(word: str, value: str) -> str | None:
    """Why a [lexicon] entry cannot be used, or None: ARPABET with stress digits."""
    example = 'like "Z AO1 R B L AE0 K S"'
    symbols = value.split()
    heads = [s.rstrip("012") for s in symbols]
    if not symbols or any(h not in VOWELS_ARPA and h not in CONSONANTS_ARPA for h in heads):
        return f"{value!r} is not ARPABET, {example}"
    vowels = [s for s, h in zip(symbols, heads) if h in VOWELS_ARPA]
    if not vowels or any(not s[-1].isdigit() for s in vowels):
        return f"{value!r} needs a stress digit on every vowel, {example}"
    return None


def lookup(norm: str) -> list[str] | None:
    candidates = [norm]
    if norm.endswith("in'"):
        candidates.append(norm[:-1] + "g")  # lovin' -> loving
    elif norm.endswith("in"):
        candidates.append(norm + "g")
    if "-" in norm:
        candidates.append(norm.replace("-", ""))
    for c in candidates:
        raw = TABLE.get(c)
        if raw:
            return raw.split("|")
    if norm.endswith("'ve"):  # shouldn't've, we'd've: the word, then [əv]
        base = lookup(norm[:-3])
        if base:
            return [v + " AH0 V" for v in base]
    if norm.endswith("'s") and len(norm) > 3:  # bustle's: the word, then its -s
        raw = TABLE.get(norm[:-2])
        if raw:
            return [v + _s_ending(v) for v in raw.split("|")]
    return None


def _s_ending(variant: str) -> str:
    last = variant.split()[-1].rstrip("012")
    if last in ("S", "Z", "SH", "ZH", "CH", "JH"):
        return " IH0 Z"
    return " S" if last in ("P", "T", "K", "F", "TH") else " Z"


def _drop_index(longer: list[str], shorter: list[str], merge: bool = False) -> int | None:
    """The vowel of longer that shorter goes without: dropped (every: EH V ER IY,
    EH V R IY), or with merge, merged into the one before it ahead of a vowel
    both share (ourselves: AW ER EH, AA EH; but not us, AH, against U.S.)."""
    for i in range(len(longer)):
        if longer[:i] + longer[i + 1 :] == shorter:
            return i
    if merge and len(shorter) == len(longer) - 1:
        for i in range(1, len(longer) - 1):
            if longer[: i - 1] == shorter[: i - 1] and longer[i + 1 :] == shorter[i:]:
                return i
    return None


def guess_syllables(token: str) -> int:
    """Syllables from spelling: vowel groups, less a silent final e or -ed."""
    return len(_counted_groups(re.sub(r"[^a-z]", "", token.lower())))


def _counted_groups(w: str) -> list[tuple[int, int]]:
    groups = [(m.start(), m.end()) for m in re.finditer(f"[{LETTER_VOWELS}]+", w)]
    if w.startswith("y") and groups and groups[0][0] == 0:
        groups[0] = (1, groups[0][1]) if groups[0][1] > 1 else groups[0]
        if groups[0][0] >= groups[0][1]:
            groups.pop(0)
    if len(groups) > 1:
        last = w[groups[-1][0] : groups[-1][1]]
        before = w[: groups[-1][0]]
        silent_e = (
            w.endswith("e")
            and last == "e"
            and not (w.endswith("le") and len(w) > 2 and w[-3] not in LETTER_VOWELS)
        )
        silent_ed = w.endswith("ed") and last == "e" and before[-1:] not in ("t", "d")
        silent_es = (
            w.endswith("es")
            and last == "e"
            and not before.endswith(("s", "z", "x", "ch", "sh", "ge", "ce"))
            and not (w.endswith("les") and len(w) > 3 and w[-4] not in LETTER_VOWELS)
        )
        if silent_e or silent_ed or silent_es:
            groups.pop()
    return groups or [(0, len(w))]


ONSETS = {
    "bl", "br", "ch", "cl", "cr", "dr", "dw", "fl", "fr", "gl", "gr", "kn", "ph", "pl", "pr",
    "qu", "sc", "sh", "sk", "sl", "sm", "sn", "sp", "st", "sw", "th", "tr", "tw", "wh", "wr",
    "scr", "shr", "spl", "spr", "squ", "str", "thr",
}  # fmt: skip


def _silent_e(low: str, groups: list[tuple[int, int]]) -> int | None:
    """The first inner e that only lengthens the vowel before it: love-ly, some-time."""
    for k in range(1, len(groups) - 1):
        a, b = groups[k]
        if low[a:b] == "e" and groups[k - 1][1] == a - 1:
            return k
    return None


def split_spelling(token: str, n: int) -> list[str]:
    """Cut the written word into n pieces that follow its vowel groups: beau-ti-ful;
    could-n't; a compound of two dictionary words at its seam: heart-ache."""
    low = token.lower()
    if n >= 2 and low.endswith(("n't", "n’t")) and len(_counted_groups(low[:-3])) < n:
        return split_spelling(token[:-3], n - 1) + [token[-3:]]
    seam = _compound_seam(low, n)
    if seam is not None:
        k, left = seam
        return split_spelling(token[:k], left) + split_spelling(token[k:], n - left)
    groups = _counted_groups(low)
    if len(groups) < n:  # a silent-looking vowel is sung after all: fi-re
        groups = [(m.start(), m.end()) for m in re.finditer(f"[{LETTER_VOWELS}]+", low)] or groups
    while len(groups) > n:
        k = _silent_e(low, groups) or len(groups) - 1
        a, b = groups[k - 1], groups.pop(k)
        groups[k - 1] = (a[0], b[1])
    while len(groups) < n:
        longest = max(range(len(groups)), key=lambda k: groups[k][1] - groups[k][0])
        a, b = groups[longest]
        if b - a < 2:
            break
        groups[longest : longest + 1] = [(a, a + 1), (a + 1, b)]
    cuts = []
    for (_, end), (start, _) in zip(groups, groups[1:]):
        gap = low[end:start]
        if start == len(low) - 1 and low.endswith("le") and len(gap) >= 2:
            onset = 2  # lit-tle, can-dle, ta-ble
        elif gap.endswith("gh"):
            onset = 0  # laugh-ing, weigh-ing
        else:
            onset = next((k for k in (3, 2) if len(gap) >= k and gap[-k:] in ONSETS), 1)
        cuts.append(start - min(onset, len(gap)))
    pieces = [token[a:b].strip("-'") or token[a:b] for a, b in zip([0, *cuts], [*cuts, len(token)])]
    while len(pieces) < n:  # too few vowel letters to cut: split the longest piece
        k = max(range(len(pieces)), key=lambda i: len(pieces[i]))
        if len(pieces[k]) < 2:
            pieces.append(pieces[k])
            continue
        half = len(pieces[k]) // 2
        pieces[k : k + 1] = [pieces[k][:half], pieces[k][half:]]
    return pieces


MIN_COMPOUND_PART = 4  # moon-light, heart-ache; not pat-ron from pat and Ron


def _compound_seam(low: str, n: int) -> tuple[int, int] | None:
    """Where low splits into two dictionary words whose syllables add up to n, and
    how many the first has; the most even such split."""
    best = None
    for k in range(MIN_COMPOUND_PART, len(low) - MIN_COMPOUND_PART + 1):
        left, right = TABLE.get(low[:k]), TABLE.get(low[k:])
        if not left or not right or not low[:k].isalpha() or not low[k:].isalpha():
            continue
        a = sum(ch.isdigit() for ch in left.split("|")[0])
        b = sum(ch.isdigit() for ch in right.split("|")[0])
        if a and b and a + b == n:
            even = abs(len(low) - 2 * k)
            if best is None or even < best[0]:
                best = (even, k, a)
    return (best[1], best[2]) if best else None


def _guess_phones(norm: str) -> tuple[str, ...]:
    """Rough phonemes from spelling, one vowel per counted vowel group."""
    w = re.sub(r"[^a-z]", "", norm)
    if not re.search(f"[{LETTER_VOWELS}]", w):
        consonants = [LETTER_PHONES[ch] for ch in w]
        return tuple(consonants[:1] + ["ə"] + consonants[1:])
    group_of = {}
    for a, b in _counted_groups(w):
        for k in range(a, b):
            group_of[k] = a
    phones: list[str] = []
    for k, ch in enumerate(w):
        if k in group_of:
            if group_of[k] == k:
                phones.append(LETTER_PHONES[ch] if ch in LETTER_VOWELS else "ə")
            continue
        if ch == "y":
            phones.append("j")
        elif ch not in LETTER_VOWELS:
            phones.append(LETTER_PHONES[ch])
    return tuple(phones)


def analyze_word(token: str, overrides: dict[str, str] | None = None) -> Word:
    norm = normalize(token)
    variants = lookup(norm)
    user = (overrides or {}).get(norm)
    if user:
        variants = [user] if any(ch.isdigit() for ch in user) else variants
    elif variants and token.lower().endswith("é"):  # résumé: the reading that sings its é
        voiced = [v for v in variants if v.split()[-1].rstrip("012") in VOWELS_ARPA]
        variants = voiced + [v for v in variants if v not in voiced]
    word = Word(token, norm, CODE, (), (), clitic=norm in CLITICS, weak=norm in WEAK)
    if not variants:
        return _guessed(word, token, norm)

    parsed = [_parse(v) for v in variants]
    # The first pronunciation counts; a longer one only when it differs by one vowel
    # that can drop (every, fire), not when it spells out an abbreviation (us: U.S.).
    longest = len(parsed[0][1])
    for _, stresses, bare in parsed[1:]:
        if len(stresses) == longest + 1 and _drop_index(bare, parsed[0][2]) is not None:
            longest += 1
            break
    if longest == 0:
        return _guessed(word, token, norm)
    full = [p for p in parsed if len(p[1]) == longest]
    for _, stresses, bare in parsed:
        if len(stresses) == longest - 1 and word.drop is None:
            word.drop = _drop_index(full[0][2], bare, merge=True)

    readings: list[Reading] = []
    for phones, stresses, _ in full:
        primary = [i for i, d in enumerate(stresses) if d == 1]
        marked = [i for i, d in enumerate(stresses) if d]
        stress = primary[-1] if primary else (marked[-1] if marked else 0)
        if longest == 1:
            stress = 0
        source = "clitic" if word.clitic else "lexicon"
        secondary = tuple(i for i in marked if i != stress)
        if readings and not marked:
            continue  # a reduced form (been as /bən/) is no reading of its own
        reading = Reading(stress, phones, norm, source, secondary)
        if all((r.stress, r.phones) != (stress, phones) for r in readings):
            readings.append(reading)  # again keeps both /əˈɡɛn/ and /əˈɡeɪn/
    # A compound may move its stress onto its second part in verse: sometíme.
    for r in list(readings):
        for k in r.secondary:
            if r.stress is not None and k > r.stress and all(x.stress != k for x in readings):
                rest = tuple(sorted({r.stress, *r.secondary} - {k}))
                readings.append(Reading(k, r.phones, norm, "shift", rest, penalty=STRESS_SHIFT))
    # Two primary stresses (well-known, thirteen) give way to a stressed word after
    # them, so the first may carry the line: a wéll-known vóice.
    for phones, stresses, _ in full[:1]:
        primary = [i for i, d in enumerate(stresses) if d == 1]
        if len(primary) > 1 and all(x.stress != primary[0] for x in readings):
            rest = tuple(i for i, d in enumerate(stresses) if d and i != primary[0])
            readings.append(Reading(primary[0], phones, norm, "shift", rest, penalty=STRESS_SHIFT))
    word.readings = tuple(readings)
    word.syllables = tuple(Syllable(p) for p in split_spelling(token, longest))
    word.weak = word.weak or word.clitic or longest == 1
    return word


def _guessed(word: Word, token: str, norm: str) -> Word:
    n = max(1, guess_syllables(norm))
    phones = _guess_phones(norm)
    word.syllables = tuple(Syllable(p) for p in split_spelling(token, n))
    order = SUFFIXES.order(re.sub(r"[^a-z]", "", norm), n)
    word.readings = tuple(Reading(p, phones, norm, "guess", penalty=c) for p, c in order)
    word.weak = word.weak or word.clitic or n == 1
    word.notes.append("not in the dictionary")
    return word
