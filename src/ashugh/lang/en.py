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
from dataclasses import replace

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
OBJECTS = {"it", "me", "you", "him", "her", "them", "us", "ya", "em"}  # find ya, need 'em
UNSTRESSED_OBJECTS = {"it", "them", "em"}  # all but never stressed: put a ring ón it
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
# Forms of be: an object pronoun after one is the predicate, stressed (it was yóu).
COPULAS = {"is", "was", "were", "are", "am", "be", "been", "being", "'s", "'re", "'m"}
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


def known(token: str) -> bool:
    """Whether the dictionary has the word, as listed or in a regular form."""
    return bool(lookup(normalize(token)))


def lookup(norm: str) -> list[str] | None:
    if norm in REPLACED:
        return list(REPLACED[norm])
    if norm.endswith("in'") and len(norm) > 4:
        # goin', blowin', cryin': the -ing word with its last sound sung [ɪn], the
        # same for all of them whatever the dictionary lists for each; vibin' as
        # vibing, which only its stem gives
        raw = TABLE.get(norm[:-1] + "g") or TABLE.get(norm)
        found = raw.split("|") if raw else _derived(norm[:-1] + "g")
        if found:
            return [_dropped_g(v) for v in found]
    candidates = [norm, norm + "'"]  # ol', the dictionary's own
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
    derived = _derived(norm)
    if derived:
        return derived
    parts = _compound_parts(norm)
    if parts:  # lovestruck, facetime: two words, stressed on the first
        left, right = ((TABLE.get(p) or "").split("|")[0] for p in parts)
        return [left + " " + right.replace("1", "2")]
    if norm.endswith("'s") and len(norm) > 3:  # bustle's: the word, then its -s
        raw = TABLE.get(norm[:-2])
        if raw:
            return [v + _s_ending(v) for v in raw.split("|")]
    return None


def _derived(norm: str) -> list[str] | None:
    """An -ed, -ing, -er, -eth or -est form the dictionary lacks, from its stem:
    ghosted, vibing, influencer, calleth, knowest (ghost, vibe, influence, call,
    know)."""
    for ending, stems in (
        ("ing", (norm[:-3], norm[:-3] + "e", norm[:-4])),
        ("ed", (norm[:-2], norm[:-1], norm[:-3], norm[:-3] + "y" if norm.endswith("ied") else "")),
        ("er", (norm[:-2], norm[:-1], norm[:-3])),
        ("eth", (norm[:-3], norm[:-3] + "e", norm[:-4])),  # calleth, loveth
        ("est", (norm[:-3], norm[:-3] + "e", norm[:-4])),  # knowest, and a superlative
    ):
        if not norm.endswith(ending) or len(norm) < len(ending) + 3:
            continue
        for stem in stems:
            raw = TABLE.get(stem) if len(stem) > 2 else None
            if not raw:
                continue
            if stem == norm[: len(stem)] and len(stem) == len(norm) - len(ending) - 1:
                if stem[-1] != norm[len(stem)]:
                    continue  # stopped: stop and a doubled p, not stopp
            return [v + _ending_phones(v, ending) for v in raw.split("|")]
    return None


def _ending_phones(variant: str, ending: str) -> str:
    last = variant.split()[-1].rstrip("012")
    if ending == "ing":
        return " IH0 NG"
    if ending == "er":
        return " ER0"
    if ending in ("eth", "est"):
        return " IH0 TH" if ending == "eth" else " IH0 S T"
    if last in ("T", "D"):
        return " IH0 D"
    return " T" if last in ("P", "K", "F", "TH", "S", "SH", "CH") else " D"


def _dropped_g(variant: str) -> str:
    phones = variant.split()
    if phones[-1:] == ["NG"]:
        phones[-1] = "N"
    if len(phones) > 1 and phones[-1] == "N" and phones[-2] in ("AH0", "IH0", "IY0"):
        phones[-2] = "IH0"
    return " ".join(phones)


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


def _reduced(stresses: list[int], vowels: list[str]) -> list[str]:
    """Vowels with the unstressed [ɪ] and [ə] alike, as a short reading may write
    them: the i of fa-vo-rite is [ɪ] in its long reading and [ə] in fav-rite."""
    return ["AH" if v == "IH" and not d else v for v, d in zip(vowels, stresses)]


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
    "scr", "shr", "spl", "spr", "squ", "str", "thr", "gh",
}  # fmt: skip


def _silent_e(low: str, groups: list[tuple[int, int]]) -> int | None:
    """The first inner e that only lengthens the vowel before it: love-ly, some-time."""
    for k in range(1, len(groups) - 1):
        a, b = groups[k]
        if low[a:b] == "e" and groups[k - 1][1] == a - 1:
            return k
    return None


def _hiatus(low: str, groups: list[tuple[int, int]]) -> bool:
    """Whether a vowel run holds two sung vowels: sci-ence, vi-o-lence."""
    return any(h in low[a:b] for h in HIATUS for a, b in groups)


def split_spelling(token: str, n: int, short: frozenset[int] = frozenset()) -> list[str]:
    """Cut the written word into n pieces that follow its vowel groups: beau-ti-ful;
    could-n't; a compound of two dictionary words at its seam: heart-ache. A
    syllable in short has a stressed short vowel, which keeps a consonant: fish-ing,
    whis-key, rec-ord (but pa-per)."""
    low = "".join(unicodedata.normalize("NFD", ch)[0] for ch in token.lower())  # èd: ed
    if n >= 2 and low.endswith(("n't", "n’t")) and len(_counted_groups(low[:-3])) < n:
        return split_spelling(token[:-3], n - 1) + [token[-3:]]
    if n >= 2 and low.endswith(("'ve", "’ve")):
        return split_spelling(token[:-3], n - 1) + [token[-3:]]  # should-n't-'ve
    if low.startswith("mc") and n >= 2 and len(_counted_groups(low)) < n:
        rest = frozenset(k - 1 for k in short if k > 0)
        return [token[:2], *split_spelling(token[2:], n - 1, rest)]  # Mc-Don-ald's
    seam = _compound_seam(low, n)
    if seam is not None:
        k, left = seam
        return split_spelling(token[:k], left) + split_spelling(token[k:], n - left)
    groups = _counted_groups(low)
    # a silent-looking vowel sung after all (fi-re, learn-ed), unless a vowel run
    # holds two (sci-ence, vi-o-lence)
    if len(groups) < n and (low.endswith(("ed", "es")) or not _hiatus(low, groups)):
        groups = _vowel_groups(low) or groups
    while len(groups) > n:
        # a silent e (love-ly), else the vowel after the first, which speech drops
        # (choco-late, came-ra), else the last
        k = _silent_e(low, groups) or (1 if len(groups) > 2 else len(groups) - 1)
        a, b = groups[k - 1], groups.pop(k)
        groups[k - 1] = (a[0], b[1])
    while len(groups) < n:  # one vowel run is two syllables: a hiatus first (Lou-i-si-a-na)
        glide = next(  # a y between vowels stays with the first: play-ing, buy-er
            (
                (k, a + m.end())
                for k, (a, b) in enumerate(groups)
                if (m := re.search(r"[aou]y(?=[aeiou])", low[a:b]))
            ),
            None,
        )
        ing = re.search(r"(?<=[aeiouy])(?=i(?:ng|ngs|n'|n’)$)", low)  # see-ing, do-ing
        ending = next(
            ((k, ing.start()) for k, (a, b) in enumerate(groups) if ing and a < ing.start() < b),
            None,
        )
        cut = (
            ending
            or glide
            or next(
                (
                    (k, a + low[a:b].find(h) + 1)
                    for h in HIATUS
                    for k, (a, b) in enumerate(groups)
                    if h in low[a:b]
                ),
                None,
            )
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
    for k, ((begin, end), (start, _)) in enumerate(zip(groups, groups[1:])):
        gap = low[end:start]
        if start == len(low) - 1 and low.endswith("le") and len(gap) >= 2:
            onset = 2  # lit-tle, can-dle, ta-ble
        elif gap == "gh" or (not gap and low[end - 1 : end] == "y"):
            onset = 0  # laugh-ing, weigh-ing; play-ing (but Lam-bor-ghi-ni)
        elif gap == "w" and low[end - 1 : end] in ("o", "e") and low[start : start + 1] == "e":
            onset = 0  # tow-er, flow-er, how-ev-er (but a-wake, to-ward)
        elif gap == "n" and low[end - 3 : end] in ("tio", "sio", "cio"):
            onset = 0  # pro-mo-tion-al, na-tion-al
        elif gap[-1:] in ("t", "s", "c", "g") and re.match(r"i[aou]", low[start : start + 2]):
            onset = 1  # na-tion, pas-sion, ma-gi-cian: the suffix keeps its consonant
        else:
            onset = next((k for k in (3, 2) if len(gap) >= k and gap[-k:] in ONSETS), 1)
            closed = re.search(r"[^aeiouy]", low[begin:end])  # some-thin': a silent e closes it
            if (
                k in short and gap and gap != "h" and not closed
            ):  # a short vowel keeps one: fish-ing
                onset = 0 if len(gap) == 1 or gap in DIGRAPHS else min(onset, len(gap) - 1)
        cuts.append(start - min(onset, len(gap)))
    # A contraction keeps its apostrophe (would-'ve, not would'-ve), and a consonant
    # before an apostrophe stays with its own syllable (rock-'n'-roll, not roc-k'n).
    cuts = [
        c - 1
        if token[c - 1 : c] in APOSTROPHES and token[c:].lower() in CONTRACTIONS
        else c + 1
        if token[c + 1 : c + 2] in APOSTROPHES and low[c : c + 1] not in LETTER_VOWELS
        else c
        for c in cuts
    ]
    bounds = list(zip([0, *cuts], [*cuts, len(token)]))
    pieces = [_piece(token[a:b], k, len(bounds)) for k, (a, b) in enumerate(bounds)]
    while len(pieces) < n:  # too few vowel letters to cut: split the longest piece
        k = max(range(len(pieces)), key=lambda i: len(pieces[i]))
        if len(pieces[k]) < 2:
            pieces.append(pieces[k])
            continue
        mark = next((j for j, ch in enumerate(pieces[k]) if j and ch in APOSTROPHES), None)
        half = mark or len(pieces[k]) // 2  # rock-'n: the apostrophe begins a syllable
        pieces[k : k + 1] = [pieces[k][:half], pieces[k][half:]]
    return pieces


def _piece(text: str, k: int, n: int) -> str:
    """A piece without the hyphens and apostrophes at its cuts; the last keeps a
    dropped g's apostrophe (fix-in') and a contraction its own (would-'ve)."""
    out = text.strip("-")
    if out.strip("'’").lower() == "n":
        return out  # the 'n' of rock 'n' roll
    if k > 0 and out.lstrip("'’").lower() not in CONTRACTIONS:
        out = out.lstrip("'’")
    if k < n - 1:
        out = out.rstrip("'’")
    return out or text


CONTRACTIONS = {"ve", "ll", "re", "d", "m", "s", "t"}
APOSTROPHES = ("'", "’")
DIGRAPHS = {"sh", "th", "ch", "ph", "ng", "ck", "wh"}
# Letter names, for an abbreviation sung letter by letter: L-A, N-Y-C, B-F-F.
LETTER_NAMES = {
    "a": "EY", "b": "B IY", "c": "S IY", "d": "D IY", "e": "IY", "f": "EH F", "g": "JH IY",
    "h": "EY CH", "i": "AY", "j": "JH EY", "k": "K EY", "l": "EH L", "m": "EH M",
    "n": "EH N", "o": "OW", "p": "P IY", "q": "K Y UW", "r": "AA R", "s": "EH S",
    "t": "T IY", "u": "Y UW", "v": "V IY", "w": "D AH B AH L Y UW", "x": "EH K S",
    "y": "W AY", "z": "Z IY",
}  # fmt: skip
# Abbreviations spelt like a word: LA is L-A, not la, wherever the line is not in capitals.
SPELLED_OUT = {"LA", "US", "AM", "PM", "ID", "RIP", "USA"}
ABBREVIATION_RE = re.compile(r"([A-Z]{2,5})(s?)")
# Words with no vowel letter that are sounds, not letters: HMM, SHH, PSST.
INTERJECTIONS = set(
    "hm hmm hmmm mm mmm mhm sh shh shhh ssh psst pst brr brrr tsk zzz grr grrr pfft pff".split()
)


def abbreviation(token: str, capitals: bool = False) -> tuple[str, bool] | None:
    """The letters of an abbreviation sung letter by letter, and whether it is a
    plural (DMs): capitals 2 to 5 long that are no word, or listed in SPELLED_OUT.
    In a line all in capitals (where AM is am), only one with no vowel letter, as
    MC, DJ and TV are anywhere; Y is a vowel there (MY, WHY, GYM) and an
    interjection is no abbreviation (HMM, PSST)."""
    m = ABBREVIATION_RE.fullmatch(token)
    if m is None:
        return None
    core = m.group(1)
    if core.lower() in INTERJECTIONS:
        return None
    if not re.search("[AEIOUY]", core):
        return core.lower(), bool(m.group(2))  # MC, DJ, TV: no word to read
    if capitals:
        return None
    if len(core) >= 4 and re.fullmatch(r"(?:[^AEIOU][AEIOU])+|(?:[AEIOU][^AEIOU])+", core):
        return None  # FOMO, YOLO, NASA: said as a word
    if TABLE.get(core.lower()) and core not in SPELLED_OUT:
        return None
    return core.lower(), bool(m.group(2))


def _name_reading(first: str, other: str) -> bool:
    """A later dictionary reading that moves the stress earlier onto a full [eɪ] or
    [iː] where the first has a reduced vowel: a surname's or a rare form (Bé-gun,
    é-lev-en), not a noun beside its verb (ádd-ress, ad-dréss)."""
    a, b = first.split(), other.split()
    va = [ph for ph in a if ph[-1:].isdigit()]
    vb = [ph for ph in b if ph[-1:].isdigit()]
    if len(va) != len(vb):
        return False
    sa = next((k for k, v in enumerate(va) if v.endswith("1")), None)
    sb = next((k for k, v in enumerate(vb) if v.endswith("1")), None)
    if sa is None or sb is None or sb >= sa:
        return False
    return vb[sb][:-1] in ("EY", "IY") and va[sb][-1] == "0"


def _letters_meant(norm: str, variants: list[str], capitals: bool) -> bool:
    """Whether capitals the dictionary reads as a word are letters after all: its
    reading says what they stand for (FYI, for your information: more syllables
    than letters), or, unless the whole line is in capitals, it spells them too
    (AKA)."""
    if len(_parse(variants[0])[1]) > len(norm):
        return True
    return not capitals and any(_letter_spelling(norm, v) for v in variants[1:])


def _letter_spelling(norm: str, variant: str) -> bool:
    """Whether a dictionary reading only spells the word's letters (ba as B.A.)."""
    names = " ".join(LETTER_NAMES.get(ch, "?") for ch in norm)
    return re.sub(r"\d", "", variant) == names


def _spelled_out(word: Word, letters: str, plural: bool) -> Word:
    """An abbreviation sung letter by letter, the last letter stressed (el-Á)."""
    phones: list[str] = []
    pieces: list[str] = []
    token = word.text
    for k, ch in enumerate(letters):
        mark = "1" if k == len(letters) - 1 else "2"
        if ch == "w":  # dou-ble-u
            phones += ["D", "AH" + mark, "B", "AH0", "L", "Y", "UW0"]
            pieces += [token[k] + "(dou", "ble", "u)"]
        else:
            phones += [p + mark if p in VOWELS_ARPA else p for p in LETTER_NAMES[ch].split()]
            pieces.append(token[k])
    if plural:
        phones.append("Z")
    pieces[-1] += token[len(letters) :]
    parsed, stresses, _ = _parse(" ".join(phones))
    stress = max(i for i, d in enumerate(stresses) if d == 1)
    word.syllables = tuple(Syllable(p) for p in pieces)
    secondary = tuple(i for i, d in enumerate(stresses) if d and i != stress)
    word.readings = (Reading(stress, parsed, word.norm, "lexicon", secondary),)
    word.weak = len(pieces) == 1
    word.spelled = True
    return word


SHORT_VOWELS = {"IH", "EH", "AE", "AH", "UH", "AA"}  # fish, bed, cat, cup, book, rock
MIN_COMPOUND_PART = 4  # moon-light, heart-ache; not pat-ron from pat and Ron
SHORT_PART = 3  # glove-box: after a silent e, the second word may be shorter
# Readings songs use that CMUdict lacks: yeah as in care, re-al, po-em in one.
EXTRA = {
    "yeah": ["Y EH1 R"],
    "real": ["R IY1 AH0 L"],
    "poem": ["P OW1 M"],
    "woah": ["W OW1"],
    "comfortable": ["K AH1 M F T ER0 B AH0 L"],  # comf-ter-ble
    "chocolate": ["CH AO1 K AH0 L AH0 T"],  # choc-o-late
    "diamond": ["D AY1 AH0 M AH0 N D"],  # di-a-mond
}
# Words the dictionary lacks or gets wrong for songs: its spring has a second
# reading in two syllables, its bae is a surname, its email stresses -mail, its Dr.
# reads drive.
REPLACED = {
    "spring": ["S P R IH1 NG"],
    "springs": ["S P R IH1 NG Z"],
    "bae": ["B EY1"],
    "email": ["IY1 M EY2 L"],
    "emails": ["IY1 M EY2 L Z"],
    "emailed": ["IY1 M EY2 L D"],
    "dr": ["D AA1 K T ER0"],
    "dr.": ["D AA1 K T ER0"],
    "mr": ["M IH1 S T ER0"],
    "mr.": ["M IH1 S T ER0"],
    "mrs": ["M IH1 S IH0 Z"],
    "mrs.": ["M IH1 S IH0 Z"],
    "yeet": ["Y IY1 T"],
    "highkey": ["HH AY1 K IY2"],
    "lowkey": ["L OW1 K IY2"],
    "rizz": ["R IH1 Z"],
    "lambo": ["L AE1 M B OW0"],
    "bussin": ["B AH1 S IH0 N"],
    "simp": ["S IH1 M P"],
    "sus": ["S AH1 S"],
    "tiktok": ["T IH1 K T AA2 K"],
    "vibe": ["V AY1 B"],
    "vibes": ["V AY1 B Z"],
    "o'er": ["OW1 R"],
    "e'en": ["IY1 N"],
    "e'er": ["EH1 R"],
    "shoulda": ["SH UH1 D AH0"],
    "coulda": ["K UH1 D AH0"],
    "woulda": ["W UH1 D AH0"],
    "musta": ["M AH1 S T AH0"],
    "sorta": ["S AO1 R T AH0"],
    "xoxo": ["EH2 K S OW2 EH2 K S OW1"],
}
# Words stressed on the first syllable as a noun or adjective and on the second
# as a verb (a récord, to recórd). The word before tells them apart; the
# dictionary lists the verb first for these, though the noun is the usual one.
NOUN_FIRST = set(
    "discount escort import impact increase insert insult perfect permit record "
    "subject survey suspect transfer transport update upgrade".split()
)
HETERONYMS = NOUN_FIRST | set(
    "address combat conduct conflict contest contract contrast convert convict desert "
    "extract object present progress project protest rebel torment recall".split()
)
VERBAL = set(
    "to i you we they he she will would can could should must might may shall 'll "
    "don't didn't won't can't cannot never gonna wanna let's please".split()
)
NOMINAL = set(
    "a an the my your his her our their its this that these those every no some any "
    "each another of in on for with at by from about".split()
)
SHORT_FIRST = {"real"}  # sung in one syllable unless the line asks two
# Abbreviations said as the words they stand for, shown in those words' syllables.
SAID_AS = {"etc": ("et", "cet", "er", "a")}
SHORT_PREFERENCE = -0.05
ARCHAIC = re.compile(r"[aeiouy]e(?:st|th)$")  # go-est, see-est, fly-eth
SYNCOPE_COST = 0.5
ALTERNATIVE_COST = 0.1  # meter cost of a dictionary reading that moves the first's stress
# An unstressed [ɚ] straight after [aɪ] or [aʊ] may merge with it, as fire and
# hour do in the dictionary's second reading: de-sire, pow'r, flow'rs.
SMOOTHED = {"AY", "AW"}
# A diphthong after the main stress keeps its full vowel, which takes a beat or
# a rhyme like a secondary stress whether or not the dictionary marks it:
# ém-pìre / fire, bírd-hòuse / mouse.
UNREDUCED = {"AY", "AW", "OY"}
HIATUS = ("ia", "io", "iu", "ie", "ua", "ue", "ui", "uo", "eo", "oe", "ea")


def _short_part_ok(low: str, k: int) -> bool:
    """A second part shorter than MIN_COMPOUND_PART after a silent e (glove-box), or
    a consonant-initial one after a consonant (Broad-way, high-way), but not an
    inflection's ending that happens to spell a word: darke-ned, withe-red."""
    if low[:k].endswith("e"):
        return not low.endswith(("ed", "es"))
    return (
        len(low) - k == SHORT_PART
        and low[k - 1] not in LETTER_VOWELS
        and low[k] not in LETTER_VOWELS
    )


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
        if a and b and a + b == n and _sounds_like_parts(low, left, right):
            even = (not low[:k].endswith("e"), abs(len(low) - 2 * k))
            if best is None or even < best[0]:
                best = (even, k, a)
    return (best[1], best[2]) if best else None


def _sounds_like_parts(low: str, left: str, right: str) -> bool:
    """Whether the word, where the dictionary has it, sounds like its two parts in a
    row (Broad-way), not merely spells them (chil-dren is no child and Ren)."""
    whole = TABLE.get(low)
    if not whole:
        return True

    def bare(variant: str) -> str:
        return re.sub(r"\d", "", variant)

    return any(
        bare(w) == f"{bare(x)} {bare(y)}"
        for w in whole.split("|")
        for x in left.split("|")
        for y in right.split("|")
    )


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


def analyze_word(
    token: str, overrides: dict[str, str] | None = None, capitals: bool = False
) -> Word:
    """One English word; capitals says its line is all in capitals (I AM is am)."""
    norm = normalize(token)
    if norm == "th" and token[1:] == "h":  # th' eternal: the, run into the next vowel
        return Word(token, norm, CODE, (), (), clitic=True, weak=True)
    variants = ["W IH1 DH"] if token == "w" else lookup(norm)  # me w/ you: with
    user = (overrides or {}).get(norm) or (overrides or {}).get(token.lower())
    spelled = None if user else abbreviation(token, capitals)
    if token == "W" and not user:
        spelled = ("w", False)  # a W: the letter, dou-ble-u
    if spelled is None and not user and variants and token.isupper() and len(norm) > 1:
        if _letter_spelling(norm, variants[0]):  # BMW: the dictionary spells it too
            spelled = (norm, False)
        elif ABBREVIATION_RE.fullmatch(token) and _letters_meant(norm, variants, capitals):
            spelled = (norm, False)
    if spelled is not None:
        return _spelled_out(Word(token, norm, CODE, (), ()), *spelled)
    if (
        variants
        and len(variants) > 1
        and token.islower()
        and re.search("[aeiouy]", norm)
        and _letter_spelling(norm, variants[0])
    ):
        variants = variants[1:]  # ba, the vocable, not B.A.; but tv has no word to read
    if variants and len(variants) > 1 and not token[:1].isupper():
        variants = [variants[0]] + [v for v in variants[1:] if not _name_reading(variants[0], v)]
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
    parts = norm.strip("-").split("-")
    whole_words = len(parts) > 1 and all(len(p) > 1 and p.isalpha() for p in parts)
    if (not variants or (whole_words and not user)) and "-" in norm.strip("-"):
        # twenty-one, ice-cold: each part as it is said, the last carrying the main
        # stress, even where the dictionary lists the whole (its twenty-one has twen)
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
    for phones, stresses, bare in parsed:
        if len(stresses) == longest - 1 and 1 in stresses:  # our as are, for the rhyme
            short_reading = Reading(stresses.index(1), phones, norm, "lexicon")
            word.short_readings = (*word.short_readings, short_reading)
        if len(stresses) == longest - 1 and word.drop is None:
            word.drop = _drop_index(full[0][2], bare, merge=True)
        for f in full if len(stresses) == longest - 1 else ():
            if word.drop is None:  # fa-vo-rite, fav-rite: a reduced vowel either way
                word.drop = _drop_index(_reduced(*f[1:]), _reduced(stresses, bare))
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
        # a later reading that moves the stress (a surname's bé-gun, é-lev-en) costs
        # the meter a little, so the usual one wins a tie
        moved = bool(readings) and stress != readings[0].stress
        reading = Reading(
            stress, phones, norm, source, secondary, penalty=ALTERNATIVE_COST if moved else 0.0
        )
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
    short = {k for k, (v, d) in enumerate(zip(bare, stresses)) if d and v in SHORT_VOWELS}
    first = next(v for v, p in zip(variants, parsed) if len(p[1]) == longest).split()
    vowel = [i for i, ph in enumerate(first) if ph[-1:].isdigit()]
    for k, at in enumerate(vowel):  # or-ange, for-est, mor-al keep the r; sto-ry does not
        if first[at] == "AO1" and first[at + 1 : at + 3] == ["R", "AH0"]:
            short.add(k)
    pieces = split_spelling(token, longest, frozenset(short))
    said = SAID_AS.get(norm)
    if said and len(said) == longest:  # etc: et-cet-er-a, not its letters cut four ways
        pieces = [token[0] + said[0][1:], *said[1:]]
    word.syllables = tuple(Syllable(p) for p in pieces)
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


def heteronyms(words: list[Word]) -> None:
    """A noun-verb pair read by the word before it: to recórd, I protést, but my
    récord, a présent; with no such word, the noun or adjective (you look
    pérfect). The other reading stays, at the meter's usual cost."""
    for k, w in enumerate(words):
        if w.lang != CODE or w.norm not in HETERONYMS or len(w.readings) < 2:
            continue
        before = words[k - 1].norm if k else ""
        if before in VERBAL:
            want = 1
        elif before in NOMINAL or w.norm in NOUN_FIRST:
            want = 0
        else:
            continue
        if not any(r.stress == want for r in w.readings):
            continue
        first = [replace(r, penalty=0.0) for r in w.readings if r.stress == want]
        rest = [
            replace(r, penalty=max(r.penalty, ALTERNATIVE_COST))
            for r in w.readings
            if r.stress != want
        ]
        w.readings = tuple(first + rest)


def sung_pieces(pieces: list[str], drop: int | None, short: bool) -> list[str]:
    """Sung pieces of an English word as Suno should read them. A syllable the line
    drops is an apostrophe (ev'-ry, diff'-rent), or runs into the one before at the
    end (fire, de-sire); one it sings that the spelling hides is written as it
    sounds (fi-er, hou-er)."""
    pieces = list(pieces)
    last = len(pieces) - 1
    if drop is None or not 0 <= drop <= last:
        return pieces
    if short and 0 < drop < last:
        cut = pieces[drop]
        at = next((k for k, ch in enumerate(cut) if ch.lower() in "aeiouy"), len(cut))
        pieces[drop - 1 : drop + 1] = [pieces[drop - 1] + cut[:at] + "'"]
        pieces[drop] = cut[at:].lstrip("aeiouyAEIOUY") + pieces[drop]
    elif short:
        at = drop - 1 if drop > 0 else 0
        pieces[at : at + 2] = ["".join(pieces[at : at + 2])]
    elif drop == last and pieces[last].lower() == "re":  # fi-re: fi-er
        pieces[last] = _case_of(pieces[last], "er")
    elif drop == last and pieces[last].lower() == "ur" and pieces[last - 1][-1:].lower() == "o":
        pieces[last - 1] += pieces[last][0]  # ho-ur: hou-er
        pieces[last] = _case_of(pieces[last], "er")
    return pieces


def _case_of(written: str, new: str) -> str:
    """new in the case written is in: FIRE's RE is ER."""
    return new.upper() if written.isupper() else new
