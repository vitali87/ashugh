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
from ..phon import is_vowel
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
# Prepositions that are stressed when they end a phrase, as particles or stranded:
# hold on, come in, what is it for. Not articles or conjunctions.
# Object pronouns: ending a line after a verb or a noun they lean on it (néed it,
# hóld me) and rhyme with it, though a song may still rhyme on them (love yóu / true).
OBJECTS = {"it", "me", "you", "him", "her", "them", "us"}
PARTICLES = {"of", "to", "in", "on", "at", "by", "for", "from", "with", "o'er"}
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
# Prepositions an object pronoun may lean past onto a content word: cáll to me.
PREPOSITIONS = set(
    "to with for at on in by from of about over after like without beside behind "
    "around into onto upon near toward towards".split()
)
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
    if norm.endswith("s") and not norm.endswith(("ss", "'s")) and len(norm) > 3:
        # lances, besieges, rhapsodies: a plural the dictionary lacks, its singular's
        for stem in (norm[:-1], norm[:-2], norm[:-3] + "y" if norm.endswith("ies") else ""):
            raw = TABLE.get(stem) if len(stem) > 1 else None
            if raw and (stem + "s" == norm or stem.endswith(("s", "x", "z", "ch", "sh", "y"))):
                return [v + _s_ending(v) for v in raw.split("|")]
    parts = _compound_parts(norm)
    if parts:  # lovestruck, facetime: two words, stressed on the first
        left, right = ((TABLE.get(p) or "").split("|")[0] for p in parts)
        return [left + " " + right.replace("1", "2")]
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


def _vowel_groups(w: str) -> list[tuple[int, int]]:
    """Runs of vowel letters; the u of qu is a consonant (qui-et, queen), and the
    e of an old -est or -eth after a vowel starts its own (go-est, fly-eth)."""
    plain = re.sub(r"(?<=q)u", "w", w)
    groups = [(m.start(), m.end()) for m in re.finditer(f"[{LETTER_VOWELS}]+", plain)]
    if groups and ARCHAIC.search(plain):
        at = len(plain) - 3
        a, b = groups[-1]
        if a < at < b:
            groups[-1:] = [(a, at), (at, b)]
    return groups


def _counted_groups(w: str) -> list[tuple[int, int]]:
    groups = _vowel_groups(w)
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
            and not before.endswith(("s", "z", "x", "ch", "sh", "g", "c"))  # fa-ces, pa-ges
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


def split_spelling(token: str, n: int, short: frozenset[int] = frozenset()) -> list[str]:
    """Cut the written word into n pieces that follow its vowel groups: beau-ti-ful;
    could-n't; a compound of two dictionary words at its seam: heart-ache. A
    syllable in short has a stressed short vowel, which keeps a consonant: fish-ing,
    whis-key, rec-ord (but pa-per)."""
    low = "".join(unicodedata.normalize("NFD", ch)[0] for ch in token.lower())  # èd: ed
    if n >= 2 and low.endswith(("n't", "n’t")) and len(_counted_groups(low[:-3])) < n:
        return split_spelling(token[:-3], n - 1) + [token[-3:]]
    seam = _compound_seam(low, n)
    if seam is not None:
        k, left = seam
        return split_spelling(token[:k], left) + split_spelling(token[k:], n - left)
    groups = _counted_groups(low)
    if len(groups) < n:  # a silent-looking vowel is sung after all: fi-re
        groups = _vowel_groups(low) or groups
    while len(groups) > n:
        k = _silent_e(low, groups) or len(groups) - 1
        a, b = groups[k - 1], groups.pop(k)
        groups[k - 1] = (a[0], b[1])
    while len(groups) < n:  # one vowel run is two syllables: a hiatus first (Lou-i-si-a-na)
        glide = next(  # a y between vowels stays with the first: play-ing, buy-er
            (
                (k, a + m.end())
                for k, (a, b) in enumerate(groups)
                if (m := re.search(r"[aeiou]y(?=[aeiou])", low[a:b]))
            ),
            None,
        )
        cut = glide or next(
            (
                (k, a + low[a:b].find(h) + 1)
                for h in HIATUS
                for k, (a, b) in enumerate(groups)
                if h in low[a:b]
            ),
            None,
        )
        if cut is None:
            longest = max(range(len(groups)), key=lambda k: groups[k][1] - groups[k][0])
            a, b = groups[longest]
            if b - a < 2:
                break
            cut = (longest, a + 1)
        k, at = cut
        a, b = groups[k]
        groups[k : k + 1] = [(a, at), (at, b)]
    cuts = []
    for k, ((_, end), (start, _)) in enumerate(zip(groups, groups[1:])):
        gap = low[end:start]
        if start == len(low) - 1 and low.endswith("le") and len(gap) >= 2:
            onset = 2  # lit-tle, can-dle, ta-ble
        elif gap.endswith("gh") or (not gap and low[end - 1 : end] == "y"):
            onset = 0  # laugh-ing, weigh-ing; play-ing
        else:
            onset = next((k for k in (3, 2) if len(gap) >= k and gap[-k:] in ONSETS), 1)
            if k in short and gap:  # the short vowel keeps one consonant, or a digraph
                onset = 0 if len(gap) == 1 or gap in DIGRAPHS else min(onset, len(gap) - 1)
        cuts.append(start - min(onset, len(gap)))
    bounds = list(zip([0, *cuts], [*cuts, len(token)]))
    pieces = [_piece(token[a:b], k, len(bounds)) for k, (a, b) in enumerate(bounds)]
    while len(pieces) < n:  # too few vowel letters to cut: split the longest piece
        k = max(range(len(pieces)), key=lambda i: len(pieces[i]))
        if len(pieces[k]) < 2:
            pieces.append(pieces[k])
            continue
        half = len(pieces[k]) // 2
        pieces[k : k + 1] = [pieces[k][:half], pieces[k][half:]]
    return pieces


def _piece(text: str, k: int, n: int) -> str:
    """A piece without the hyphens and apostrophes at its cuts; the last keeps a
    dropped g's apostrophe (fix-in')."""
    out = text.strip("-")
    if k > 0:
        out = out.lstrip("'’")
    if k < n - 1:
        out = out.rstrip("'’")
    return out or text


DIGRAPHS = {"sh", "th", "ch", "ph", "ng", "ck", "wh"}
SHORT_VOWELS = {"IH", "EH", "AE", "AH", "UH", "AA"}  # fish, bed, cat, cup, book, rock
MIN_COMPOUND_PART = 4  # moon-light, heart-ache; not pat-ron from pat and Ron
SHORT_PART = 3  # glove-box: after a silent e, the second word may be shorter
# Readings songs use that CMUdict lacks: yeah as in care, re-al, po-em in one.
EXTRA = {"yeah": ["Y EH1 R"], "real": ["R IY1 AH0 L"], "poem": ["P OW1 M"]}
SHORT_FIRST = {"real"}  # sung in one syllable unless the line asks two
SHORT_PREFERENCE = -0.05
ARCHAIC = re.compile(r"[aeiouy]e(?:st|th)$")  # go-est, see-est, fly-eth
SYNCOPE_COST = 0.5
# An unstressed [ɚ] straight after [aɪ] or [aʊ] may merge with it, as fire and
# hour do in the dictionary's second reading: de-sire, pow'r, flow'rs.
SMOOTHED = {"AY", "AW"}
# A diphthong after the main stress keeps its full vowel, which takes a beat or
# a rhyme like a secondary stress whether or not the dictionary marks it:
# ém-pìre / fire, bírd-hòuse / mouse.
UNREDUCED = {"AY", "AW", "OY"}
HIATUS = ("ia", "io", "iu", "ie", "ua", "ue", "ui", "uo", "eo", "oe", "ea")


def _short_part_ok(low: str, k: int) -> bool:
    """A second part shorter than MIN_COMPOUND_PART after a silent e (glove-box), but
    not an inflection's ending that happens to spell a word: darke-ned, withe-red."""
    return low[:k].endswith("e") and not low.endswith(("ed", "es"))


def _compound_parts(low: str) -> tuple[str, str] | None:
    """A word the dictionary lacks as two words it has, the most even split."""
    if not low.isalpha() or len(low) < 2 * MIN_COMPOUND_PART:
        return None
    best = None
    for k in range(MIN_COMPOUND_PART, len(low) - SHORT_PART + 1):
        if len(low) - k < MIN_COMPOUND_PART and not _short_part_ok(low, k):
            continue
        if TABLE.get(low[:k]) and TABLE.get(low[k:]):
            even = (not low[:k].endswith("e"), abs(len(low) - 2 * k))  # love-struck
            if best is None or even < best[0]:
                best = (even, k)
    return (low[: best[1]], low[best[1] :]) if best else None


def _compound_seam(low: str, n: int) -> tuple[int, int] | None:
    """Where low splits into two dictionary words whose syllables add up to n, and
    how many the first has; the most even such split."""
    best = None
    for k in range(MIN_COMPOUND_PART, len(low) - SHORT_PART + 1):
        if len(low) - k < MIN_COMPOUND_PART and not _short_part_ok(low, k):
            continue
        left, right = TABLE.get(low[:k]), TABLE.get(low[k:])
        if not left or not right or not low[:k].isalpha() or not low[k:].isalpha():
            continue
        a = sum(ch.isdigit() for ch in left.split("|")[0])
        b = sum(ch.isdigit() for ch in right.split("|")[0])
        if a and b and a + b == n:
            even = (not low[:k].endswith("e"), abs(len(low) - 2 * k))
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
    user = (overrides or {}).get(norm) or (overrides or {}).get(token.lower())
    if norm in EXTRA and not user:
        variants = (variants or []) + [v for v in EXTRA[norm] if v not in (variants or [])]
    if user:
        variants = [user] if any(ch.isdigit() for ch in user) else variants
    elif variants and token.lower().endswith("èd"):  # blessèd, wingèd: the -ed is sung
        variants = list(dict.fromkeys(_sung_ed(v) for v in variants))
    elif variants and token.lower().endswith("é"):  # résumé: the reading that sings its é
        voiced = [v for v in variants if v.split()[-1].rstrip("012") in VOWELS_ARPA]
        variants = voiced + [v for v in variants if v not in voiced]
    word = Word(token, norm, CODE, (), (), clitic=norm in CLITICS, weak=norm in WEAK)
    if not variants and "-" in norm.strip("-"):
        return _hyphenated(word, token, overrides)
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
    vowels, marks = full[0][2], full[0][1]
    if word.drop is None and len(vowels) >= 3 and vowels[-2:] == ["ER", "IY"] and marks[-2] == 0:
        word.drop = len(vowels) - 2  # mem'ry, myst'ry: an unstressed er before a final y
        word.drop_cost = SYNCOPE_COST  # a licence, taken when the line needs it
    if word.drop is None and _smoothed(*full[0]):
        word.drop = len(vowels) - 1
    if norm in SHORT_FIRST and word.drop is not None:
        word.drop_cost = SHORT_PREFERENCE

    readings: list[Reading] = []
    for phones, stresses, bare in full:
        primary = [i for i, d in enumerate(stresses) if d == 1]
        marked = [i for i, d in enumerate(stresses) if d]
        stress = primary[-1] if primary else (marked[0] if marked else 0)  # ín-sta-gràm
        if longest == 1:
            stress = 0
        source = "clitic" if word.clitic else "lexicon"
        full_vowels = [i for i, v in enumerate(bare) if i > stress and v in UNREDUCED]
        secondary = tuple(sorted({i for i in marked if i != stress} | set(full_vowels)))
        if readings and not marked:
            continue  # a reduced form (been as /bən/) is no reading of its own
        reading = Reading(stress, phones, norm, source, secondary)
        if all((r.stress, r.phones) != (stress, phones) for r in readings):
            readings.append(reading)  # again keeps both /əˈɡɛn/ and /əˈɡeɪn/
    # A compound may move its stress onto its second part in verse (sometíme), but no
    # other word may (pró-gram, áth-lete); and a word stressed late may move it onto an
    # earlier secondary before a stressed word (the rhythm rule: Ténnessee whiskey, a
    # Jápanese garden), which the meter takes only where such a word follows.
    compound = _compound_parts(norm) is not None
    for r in list(readings):
        for k in r.secondary:
            if r.stress is not None and k > r.stress and not compound:
                continue
            if r.stress is not None and k != r.stress and all(x.stress != k for x in readings):
                rest = tuple(sorted({r.stress, *r.secondary} - {k}))
                kind = "shift" if k > r.stress else "clash"
                readings.append(Reading(k, r.phones, norm, kind, rest, penalty=STRESS_SHIFT))
    # Two primary stresses (well-known, thirteen) give way to a stressed word after
    # them, so the first may carry the line: a wéll-known vóice.
    for phones, stresses, _ in full[:1]:
        primary = [i for i, d in enumerate(stresses) if d == 1]
        if len(primary) > 1 and all(x.stress != primary[0] for x in readings):
            rest = tuple(i for i, d in enumerate(stresses) if d and i != primary[0])
            readings.append(Reading(primary[0], phones, norm, "clash", rest, penalty=STRESS_SHIFT))
    word.readings = tuple(readings)
    _, stresses, bare = full[0]
    short = frozenset(k for k, (v, d) in enumerate(zip(bare, stresses)) if d and v in SHORT_VOWELS)
    word.syllables = tuple(Syllable(p) for p in split_spelling(token, longest, short))
    word.weak = word.weak or word.clitic or longest == 1
    return word


def _hyphenated(word: Word, token: str, overrides: dict[str, str] | None) -> Word:
    """A hyphenated word the dictionary lacks, read part by part: the last
    stressed part carries the stress and the rhyme, the parts before keep theirs
    as secondary stresses (ice-cóld, twenty-four-séven); a clitic part takes
    none (up-to-dáte)."""
    parts = [analyze_word(p, overrides) for p in token.split("-") if p.strip("'")]
    offsets = [sum(p.size for p in parts[:k]) for k in range(len(parts))]
    stressed = [k for k, p in enumerate(parts) if not p.clitic and p.size]
    last = stressed[-1] if stressed else len(parts) - 1
    before = [
        offsets[k] + s
        for k in stressed
        if k != last
        for s in {parts[k].readings[0].stress, *parts[k].readings[0].secondary}
        if s is not None
    ]
    head = tuple(ph for p in parts[:last] for ph in p.readings[0].phones)
    tail = tuple(ph for p in parts[last + 1 :] for ph in p.readings[0].phones)
    readings = []
    for r in parts[last].readings:
        stress = None if r.stress is None else offsets[last] + r.stress
        own = [offsets[last] + k for k in r.secondary]
        secondary = tuple(sorted(set(before + own) - {stress}))
        readings.append(
            Reading(stress, head + r.phones + tail, word.norm, r.source, secondary, r.penalty)
        )
    # Before a stressed noun, or as a compound noun, the first part takes the main
    # stress: a lóng-lost friend, at clósing-time; the meter takes it as a licence.
    for k in stressed[:-1]:
        first = parts[k].readings[0].stress
        if first is None:
            continue
        stress = offsets[k] + first
        secondary = tuple(
            sorted({*before, offsets[last] + (parts[last].readings[0].stress or 0)} - {stress})
        )
        phones = readings[0].phones if readings else ()
        readings.append(Reading(stress, phones, word.norm, "shift", secondary, STRESS_SHIFT))
    word.readings = tuple(readings)
    word.syllables = tuple(s for p in parts for s in p.syllables)
    dropping = next((k for k, p in enumerate(parts) if p.drop is not None), None)
    if dropping is not None:
        word.drop = offsets[dropping] + (parts[dropping].drop or 0)
        word.drop_cost = parts[dropping].drop_cost
    word.weak = word.weak or word.size == 1
    return word


def _sung_ed(variant: str) -> str:
    """blessed with its -ed sung: B L EH1 S T as B L EH1 S IH0 D."""
    phones = variant.split()
    if len(phones) > 1 and phones[-1] in ("T", "D") and phones[-2].rstrip("012") not in VOWELS_ARPA:
        return " ".join([*phones[:-1], "IH0", "D"])
    return variant


def _smoothed(phones: tuple[str, ...], stresses: list[int], bare: list[str]) -> bool:
    """Whether the last vowel is an unstressed er right after aɪ or aʊ."""
    if len(bare) < 2 or bare[-1] != "ER" or stresses[-1] or bare[-2] not in SMOOTHED:
        return False
    at = [i for i, p in enumerate(phones) if is_vowel(p)]
    return at[-1] == at[-2] + 1


def _guessed(word: Word, token: str, norm: str) -> Word:
    n = max(1, guess_syllables(norm))
    phones = _guess_phones(norm)
    word.syllables = tuple(Syllable(p) for p in split_spelling(token, n))
    order = SUFFIXES.order(re.sub(r"[^a-z]", "", norm), n)
    word.readings = tuple(Reading(p, phones, norm, "guess", penalty=c) for p, c in order)
    word.weak = word.weak or word.clitic or n == 1
    word.notes.append("not in the dictionary")
    return word
