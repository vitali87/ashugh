"""Eastern Armenian: letters to phonemes, hidden-schwa epenthesis, syllables, stress.

Armenian writes almost none of its schwas. Մկրտիչ has one vowel letter and is
sung mə-kər-tich; սպասել is ըս-պա-սել. The rules this module applies:

* A word-initial ս, զ or շ before a stop or affricate takes a schwa in front of
  it (prothesis): սպասել -> ըս-պա-սել, ստվեր -> ըս-տը-վեր.
* Otherwise every consonant cluster is split into a coda for the vowel before
  it, an onset for the vowel after it, and as few schwa syllables as possible
  in between. An onset is one consonant, or a consonant plus յ (կյանք). A coda
  is at most two consonants that do not rise in sonority (սիրտ, միտք, but
  տետր -> տե-տըր, աստղ -> աս-տըղ). A word does not end in մն or ռն:
  ուրեմն -> ու-րե-մըն, սառն -> սա-ռըն.
* Word-final ս or դ after a consonant other than յ is the possessive suffix
  and takes a schwa: սիրտս -> սիր-տըս, գլուխդ -> գը-լու-խըդ, սերդ -> սե-րըդ,
  տունդ -> տու-նըդ. Not in words whose stem ends that way (չորս, լույս, մարդ,
  ադամանդ, մաքս), listed from Wiktionary's dictionary forms in
  data/hy_lexical.tsv, compounds that end in one of them (միջնաբերդ), and
  agent nouns and ordinals in -որդ (վարորդ, հինգերորդ), and longer nouns
  in -ուրդ (ժողովուրդ).
* The negative prefix ան- before ս, զ or շ and a stop keeps the stem's
  schwa: անշտապ -> ան-շը-տապ.
* A compound keeps the schwa of its second root (մեղադրել -> մե-ղա-դը-րել,
  from դրել). No rule predicts that, so word beginnings that do it are
  listed from Wiktionary in data/hy_compound.tsv; any word that starts with
  one gets the schwa, inflected or not (մե-ղա-դը-րան-քը). Speech often drops
  it, so a line may sing it or not.
* Ties between equally short splits go to the longer onset (-թյուն), then to
  the split whose codas are longest reading from the right (Մկրտիչ ->
  մը-կըր-տիչ, Ադրբեջան -> ա-դըր-բե-ջան).

Stress falls on the last syllable whose vowel is not a schwa. The marks ՛ ՜ ՞
written after a vowel move it there.

Other schwas that come from morphology rather than from the cluster
(կայսրություն keeps the schwa of կայսր) are out of reach of these rules; the
spec's [lexicon] table fixes them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from functools import cache
from importlib import resources

from .. import lyrics
from ..model import Reading, Syllable, Word
from ..phon import features, is_obstruent, is_stop, sonority

CODE = "hy"
NAME = "Armenian"

STRESS_MARKS = {"\u055b", "\u055c", "\u055e"}  # ՛ ՜ ՞

LETTERS = {
    "ա": "a",
    "բ": "b",
    "գ": "g",
    "դ": "d",
    "զ": "z",
    "է": "e",
    "ը": "ə",
    "թ": "tʰ",
    "ժ": "ʒ",
    "ի": "i",
    "լ": "l",
    "խ": "χ",
    "ծ": "ts",
    "կ": "k",
    "հ": "h",
    "ձ": "dz",
    "ղ": "ʁ",
    "ճ": "tʃ",
    "մ": "m",
    "յ": "j",
    "ն": "n",
    "շ": "ʃ",
    "չ": "tʃʰ",
    "պ": "p",
    "ջ": "dʒ",
    "ռ": "r",
    "ս": "s",
    "վ": "v",
    "տ": "t",
    "ր": "ɾ",
    "ց": "tsʰ",
    "ւ": "v",
    "փ": "pʰ",
    "ք": "kʰ",
    "օ": "o",
    "ֆ": "f",
}
VOWEL_PHONES = {"a", "e", "i", "o", "u", "ə"}

# Word-initial ե is [je] and ո is [vo], except in these words.
NO_YOD = {"եմ", "ենք", "եք", "են"}
NO_VO = {"ով", "ովքեր"}

# The auxiliary "to be": no stress of its own, leans on the word before it.
AUXILIARIES = {"եմ", "ես", "է", "ենք", "եք", "են", "էի", "էիր", "էր", "էինք", "էիք", "էին", "ա"}
# ա is speech's է (լավ ա, սիրում ա), sung in rap, rabiz and pop alike.
CLITICS = AUXILIARIES | {"ու", "և", "եւ", "եվ", "էլ", "թե", "որ", "մի", "ի"}  # Եվ opens a sentence

PROTHESIS_FIRST = {"s", "z", "ʃ"}
MAX_CODA = 2
# A word may end on three consonants that fall in sonority, or on ս between
# stops: Մինսկ, պարտք, կուրծք, տեքստ, Մարքս. Not where it rises: աս-տըղ, բար-ձըր.
MAX_FINAL_CODA = 3
# The possessive ս (my) and դ (your) take a schwa after a sonorant too: սե-րըս,
# տու-նըդ, սե-րըդ. Not after յ (լույս, հույս), and not in the words of
# data/hy_lexical.tsv and these, whose stem ends that way.
POSSESSIVE_AFTER = {"ɾ", "r", "n", "l", "ʁ", "m"}
# Agent nouns and ordinals in -որդ (վարորդ, հինգերորդ), and nouns in -ուրդ
# after a stem of three letters or more (ժողովուրդ, but հյուր-դ, ջուր-դ).
LEXICAL_SUFFIXES = (("որդ", 3), ("ուրդ", 7))
# A compound joined by ա or ե ends in a listed stem: նորա-հարս, դափնե-վարդ;
# but not հա-մարդ (your number) or մա-զերդ (your hair).
LINKERS = ("ա", "ե")
MIN_HEAD = 3
# Possessives the dictionary also lists as stems: յար-դ (your beloved), not straw.
POSSESSIVE_FORMS = {"յարդ"}
MIN_COMPOUND = 4  # the shortest listed word beginning
MIN_ROOT = 4  # the shortest listed root that opens on a cluster: նշան, սղոց
# Final clusters Wiktionary splits with a schwa in 19 of 21 dictionary forms.
FINAL_SPLIT = {("m", "n"), ("r", "n")}
NOT_POSSESSIVE = {
    "չորս", "ներս", "դուրս", "որս", "ձկնորս", "թարս", "կարս", "կուրս", "մարս", "ֆարս",
    "ռեսուրս", "կոնկուրս", "դիսկուրս", "շանս", "բալանս", "ռոմանս", "ֆինանս", "սեանս",
    "ավանս", "նյուանս", "դիստանս", "ռեվերանս", "ալյանս", "վալս", "պուլս", "ֆոնդ",
    "բրենդ", "լեգենդ", "տրենդ", "սթենդ", "հարս", "վարս", "պարս", "ռեզոնանս",
    "կոնֆերանս", "ռենեսանս", "ծնունդ", "սերունդ", "գունդ", "հունդ", "փունդ", "խանդ",
    "ընդ", "դիվիդենդ", "պոնդ", "հոլանդ",
    # names from other languages, sung as they are spelled
    "էդուարդ", "ռոնալդ", "արնոլդ", "էդմոնդ", "լեոնարդ", "բեռնարդ", "ջերալդ", "դոնալդ",
    "հարոլդ", "ռայմոնդ", "էդգարդ", "ջեյմս", "հանս", "ջոնս", "ռիչարդ", "էդվարդ",
    "ժերարդ", "գերհարդ", "էրհարդ",
    "նուարդ", "նվարդ",  # and Armenian ones
}  # fmt: skip


@dataclass
class Seg:
    ph: str
    src: str  # the letters it is written with ("" for the յ of initial ե)
    vowel: bool
    epenthetic: bool = False
    stressed: bool = False  # a stress mark follows its vowel
    ligature: bool = False  # one half of և


def is_armenian(ch: str) -> bool:
    # The Armenian block, U+0531 to U+058F, and the ligatures U+FB13 to U+FB17.
    return "Ա" <= ch <= "֏" or "ﬓ" <= ch <= "ﬗ"


def normalize(word: str) -> str:
    return "".join(ch for ch in word.lower() if ch not in STRESS_MARKS)


def segments(word: str) -> list[Seg]:
    norm = normalize(word)
    segs: list[Seg] = []
    chars = list(word)
    i = 0
    while i < len(chars):
        ch = chars[i]
        low = ch.lower()
        if ch in STRESS_MARKS:
            # on the vowel before it, but never a schwa: սարը՜ is սա́րը, an exclamation
            # over the word, as Armenian stresses no ը
            for seg in reversed(segs):
                if seg.vowel and seg.ph != "ə":
                    seg.stressed = True
                    break
            i += 1
            continue
        first = not segs
        after_vowel = bool(segs) and segs[-1].vowel
        if low == "ո" and i + 1 < len(chars) and chars[i + 1].lower() == "ւ":
            segs.append(Seg("u", ch + chars[i + 1], True))
            i += 2
            continue
        if (
            low == "ո"
            and "".join(chars[i + 1 : i + 3]).lower()[1:] == "ւ"
            and chars[i + 1] in STRESS_MARKS
        ):
            segs.append(Seg("u", ch + chars[i + 2], True, stressed=True))  # ո՞ւ
            i += 3
            continue
        if low == "ո":
            if first and norm not in NO_VO:
                segs.append(Seg("v", "", False))
            segs.append(Seg("o", ch, True))
        elif low == "ե":
            if (first and norm not in NO_YOD) or after_vowel:
                segs.append(Seg("j", "", False))
            segs.append(Seg("e", ch, True))
        elif low == "և":
            if first or after_vowel:
                segs.append(Seg("j", "", False))
            segs.append(Seg("e", "Ե" if ch.isupper() else "ե", True, ligature=True))
            segs.append(Seg("v", "վ", False, ligature=True))
        elif low in LETTERS:
            ph = LETTERS[low]
            segs.append(Seg(ph, ch, ph in VOWEL_PHONES))
        i += 1
    return segs


def _schwa() -> Seg:
    return Seg("ə", "ը", True, epenthetic=True)


def _valid_coda(
    cs: list[Seg], final: bool, possessive: bool = True, before: str | None = None
) -> bool:
    """Whether cs may close a syllable; before is the consonant that follows it, if any."""
    if len(cs) > (MAX_FINAL_CODA if final else MAX_CODA):
        return False
    if len(cs) == 3:
        a, b = cs[0].ph, cs[1].ph
        if sonority(a) < sonority(b) and b != "s":
            return False
        return _valid_coda(cs[1:], final, possessive)
    if len(cs) == 2:
        a, b = cs[0].ph, cs[1].ph
        if final and (a, b) in FINAL_SPLIT:
            return False
        if before is not None and (a.replace("ɾ", "r"), b) == ("r", "n") and before != "tsʰ":
            return False  # ա-ռըն-չել, ձեռ-նը-տու: no ռն or րն before a consonant (but լեռն-ցի)
        if sonority(a) < sonority(b) and not (final and not possessive and b == "s"):
            fric_m = b == "m" and features(a).manner == "fric"
            if not (fric_m and (final or before == "n")):
                return False  # a stem may end in a stop and ս (մաքս), a fricative and մ
                # (կողմ), which stays before ն too (կողմ-նա-կի)
        if final and possessive and _possessive(a, b):
            return False
    return True


def _possessive(a: str, b: str) -> bool:
    """Whether a final consonant pair reads as a stem plus the possessive ս or դ."""
    return b in ("s", "d") and (is_obstruent(a) or a in POSSESSIVE_AFTER)


@cache
def short_words() -> frozenset[str]:
    """Words of two to five letters, so one written in capitals for emphasis (ՔԵԶ,
    ԻՆՁ) is no abbreviation."""
    text = resources.files("ashugh").joinpath("data/hy_short.tsv").read_text(encoding="utf-8")
    return frozenset(text.split())


@cache
def lexical_endings() -> frozenset[str]:
    """Words whose final ս or դ belongs to the stem."""
    text = resources.files("ashugh").joinpath("data/hy_lexical.tsv").read_text(encoding="utf-8")
    return frozenset(text.split()) | NOT_POSSESSIVE


@cache
def compound_schwas() -> frozenset[str]:
    """Word beginnings with a schwa before their last letter: մեղադր (մե-ղա-դը-րել)."""
    text = resources.files("ashugh").joinpath("data/hy_compound.tsv").read_text(encoding="utf-8")
    return frozenset(text.split())


@cache
def cluster_roots() -> frozenset[str]:
    """Words that open on two consonants with a schwa between (նշան, սղոց)."""
    text = resources.files("ashugh").joinpath("data/hy_roots.tsv").read_text(encoding="utf-8")
    return frozenset(text.split())


def root_points(norm: str, roots: frozenset[str] | set[str]) -> list[int]:
    """Segment indices of the schwas that roots keep after a compound's linker
    ա or ե: լու-սա-նը-շան (նշան), բեն-զա-սը-ղոց (սղոց)."""
    out = set()
    for k in range(MIN_HEAD, len(norm) - MIN_ROOT + 1):
        if norm[k - 1] in LINKERS and any(
            norm[k:j] in roots for j in range(k + MIN_ROOT, len(norm) + 1)
        ):
            out.add(len(segments(norm[: k + 1])))
    # the negative ան- keeps its root's schwa too: ան-շը-նորհք, ան-սը-խալ, ան-խը-ռով
    if norm.startswith("ան") and any(
        norm[2:j] in roots for j in range(2 + MIN_ROOT, len(norm) + 1)
    ):
        out.add(len(segments(norm[:3])))
    return sorted(out)


def compound_points(norm: str) -> list[int]:
    """Segment indices to put a compound's schwa before, last first."""
    keys = compound_schwas()
    found = (norm[:k] for k in range(MIN_COMPOUND, len(norm) + 1) if norm[:k] in keys)
    points = {len(segments(key)) - 1 for key in found} | set(root_points(norm, cluster_roots()))
    return sorted(points, reverse=True)


def stem_final(norm: str) -> bool:
    """Whether a final ս or դ of norm is the stem's own rather than the possessive."""
    if norm in POSSESSIVE_FORMS:
        return False
    if norm.endswith("քս") and norm[-3:-2] in "աեէըիոօու":
        # ինդեքս, պարադոքս, միքս, ֆաքս, ռեմիքս: a loanword's stem; but a longer
        # word in -աք or -իք takes the possessive (քաղա-քըս, հայրենի-քըս)
        vowels = sum(seg.vowel for seg in segments(norm))
        return norm[-3:-2] in "եէոօ" or vowels == 1 or norm.endswith("միքս")
    words = lexical_endings()
    if norm in words or any(norm.endswith(s) and len(norm) >= n for s, n in LEXICAL_SUFFIXES):
        return True
    return any(
        norm[k:] in words for k in range(MIN_HEAD, len(norm) - 2) if norm[k - 1 : k] in LINKERS
    ) or any(norm.startswith(h) and norm[len(h) :] in words for h in COMPOUND_HEADS)


# Heads of compounds with no linker: the tens of քսանչորս, երեսունչորս, and գեր- of
# գերմարդ, before a stem whose final ս or դ is its own.
COMPOUND_HEADS = (
    "քսան", "երեսուն", "քառասուն", "հիսուն", "վաթսուն", "յոթանասուն", "ութսուն", "իննսուն",
    "տասն", "գեր",
)  # fmt: skip


def _onsets(cs: list[Seg]) -> list[int]:
    """Possible onset lengths for the vowel after cluster cs."""
    if not cs:
        return [0]
    options = [1]
    if len(cs) >= 2 and cs[-1].ph == "j" and cs[-2].ph != "j":
        options.append(2)
    return options


def _schwa_run(
    cs: list[Seg], closed_last: bool, possessive: bool = True
) -> list[tuple[list[Seg], list[Seg]]] | None:
    """The best way to cut cs into schwa syllables (onset, coda), or None: the
    fewest syllables, then the fewest that open on յ, then, right to left, the
    longer coda (մը-կըր-տիչ, not մըկ-րը-տիչ). The best cut of each prefix is
    found once, so a long cluster costs time in its length, not in its cuts."""
    n = len(cs)
    if not n:
        return []
    best: list[tuple | None] = [(0, 0, (), [])] + [None] * n  # by prefix length
    for i in range(1, n + 1):
        last = i == n  # only the cluster's last syllable may close a word
        closed = closed_last and last
        found = None
        for coda_len in range(0, min(MAX_CODA, i - 1) + 1):
            rest = i - 1 - coda_len
            onset, coda = cs[rest : rest + 1], cs[rest + 1 : i]
            head = best[rest]
            if head is None or (closed and not coda):
                continue
            if not _valid_coda(coda, final=closed, possessive=possessive if last else True):
                continue
            if len(coda) == 2 and not is_stop(coda[1].ph):
                continue  # զը-րըն-գալ, բը-ժըշ-կել, but մը-կըրտ-չյան, հընդ-կաս-տան
            key = (head[0] + 1, head[1] + (onset[0].ph == "j"), (-len(coda),) + head[2])
            if found is None or key < found[:3]:
                found = (*key, head[3] + [(onset, coda)])
        best[i] = found
    done = best[n]
    return done[3] if done else None


def _parse_cluster(cs: list[Seg], has_prev: bool, has_next: bool, possessive: bool = True):
    """Split a consonant cluster into (coda, schwa syllables, onset)."""
    best = None
    for onset_len in _onsets(cs) if has_next else [0]:
        onset = cs[len(cs) - onset_len :] if onset_len else []
        inner = cs[: len(cs) - onset_len]
        longest = MAX_CODA if has_next else MAX_FINAL_CODA
        coda_lens = range(0, min(longest, len(inner)) + 1) if has_prev else [0]
        for coda_len in coda_lens:
            coda = inner[:coda_len]
            final = not has_next
            after = (inner[coda_len:] + onset)[:1]
            before = after[0].ph if after else None
            if has_prev and not _valid_coda(coda, final, possessive, before):
                continue
            run = _schwa_run(inner[coda_len:], not has_next, possessive=possessive)
            if run is None:
                continue
            yod = sum(1 for o, _ in run if o[0].ph == "j")
            # Right to left, the longer coda wins: մը-կըր-տիչ, not մըկ-րը-տիչ.
            codas = tuple(-len(c) for _, c in reversed(run)) + (-coda_len,)
            score = (len(run), yod, -onset_len, codas)
            if best is None or score < best[0]:
                best = (score, coda, run, onset)
    if best is None:
        return None
    return best[1], best[2], best[3]


def _negative_prefix(segs: list[Seg], cluster: list[Seg]) -> bool:
    """ան- before a stem that opens on ս, զ or շ and a stop: ան-շը-տապ, ան-սը-պա-սե-լի."""
    return (
        bool(segs)
        and segs[0].ph == "a"
        and len(cluster) >= 3
        and cluster[0].ph == "n"
        and cluster[1].ph in PROTHESIS_FIRST
        and is_stop(cluster[2].ph)
    )


def _ver_prefix(segs: list[Seg], v: int, cluster: list[Seg]) -> bool:
    """վեր- before a stem that opens on ս, զ or շ and a stop: վերստին, վերսկսել."""
    return (
        v == 1
        and [s.ph for s in segs[:2]] == ["v", "e"]
        and len(cluster) >= 3
        and cluster[0].ph == "ɾ"
        and cluster[1].ph in PROTHESIS_FIRST
        and is_stop(cluster[2].ph)
        and not _schwa_after(cluster[1].ph, cluster[2].ph)
    )


def _schwa_after(first: str, stop: str) -> bool:
    return (first == "ʃ" and stop.endswith("ʰ")) or (first == "z" and stop in ("p", "t", "k"))


def syllabify(segs: list[Seg], possessive: bool = True) -> list[list[Seg]]:
    vowels = [i for i, s in enumerate(segs) if s.vowel]
    if not vowels:
        # No vowel letter at all: one schwa after the first consonant.
        return [segs[:1] + [_schwa()] + segs[1:]] if segs else []

    syllables: list[list[Seg]] = []
    lead = segs[: vowels[0]]
    # Prothesis: ս/զ/շ + stop at the start of the word; but շ before an aspirate and զ
    # before a voiceless stop take the schwa after them (շը-քեղ, զը-տել).
    while (
        len(lead) >= 2
        and lead[0].ph in PROTHESIS_FIRST
        and is_stop(lead[1].ph)
        and not _schwa_after(lead[0].ph, lead[1].ph)
    ):
        syllables.append([_schwa(), lead[0]])
        lead = lead[1:]
    parsed = _parse_cluster(lead, has_prev=False, has_next=True)
    if parsed is None:
        parsed = ([], [(lead[i : i + 1], []) for i in range(len(lead) - 1)], lead[-1:])
    _, run, onset = parsed
    syllables.extend(o + [_schwa()] + c for o, c in run)
    current = onset + [segs[vowels[0]]]

    for k, v in enumerate(vowels):
        end = vowels[k + 1] if k + 1 < len(vowels) else len(segs)
        cluster = segs[v + 1 : end]
        has_next = k + 1 < len(vowels)
        if k == 0 and has_next and _ver_prefix(segs, v, cluster):
            # վեր- keeps its stem's leading schwa: վե-րըս-տին, վե-րըս-կը-սել
            syllables.append(current)
            syllables.append([cluster[0], _schwa(), cluster[1]])
            rest = cluster[2:]
            parsed = _parse_cluster(rest, has_prev=False, has_next=True)
            _, run, onset = parsed if parsed else ([], [], rest)
            syllables.extend(o + [_schwa()] + c for o, c in run)
            current = onset + [segs[end]]
            continue
        if v == 0 and has_next and _negative_prefix(segs, cluster):
            syllables.append(current + cluster[:1])  # the stem keeps its schwa
            syllables.append(cluster[1:2] + [_schwa()])
            current, cluster = [], cluster[2:]
            parsed = _parse_cluster(cluster, has_prev=False, has_next=True)
            _, run, onset = parsed if parsed else ([], [], cluster)
            syllables.extend(o + [_schwa()] + c for o, c in run)
            current = onset + [segs[end]]
            continue
        parsed = _parse_cluster(cluster, has_prev=True, has_next=has_next, possessive=possessive)
        if parsed is None:  # cannot happen with MAX_CODA >= 1, kept as a guard
            parsed = (cluster, [], [])
        coda, run, onset = parsed
        current.extend(coda)
        syllables.append(current)
        syllables.extend(o + [_schwa()] + c for o, c in run)
        current = onset + ([segs[end]] if has_next else [])
    return syllables


def _display(syllables: list[list[Seg]], original: str, caps: bool = True) -> list[Syllable]:
    out = []
    for syl in syllables:
        parts = []
        for k, s in enumerate(syl):
            whole = s.ligature and s.ph == "e" and k + 1 < len(syl) and syl[k + 1].ligature
            if s.ligature and s.ph == "v" and k > 0 and syl[k - 1].ligature:
                continue  # drawn with its ե as one և
            parts.append("և" if whole else s.src)
        phones = tuple(s.ph for s in syl)
        out.append(Syllable("".join(parts), any(s.epenthetic for s in syl), phones))
    if caps and len(original) > 1 and original.isupper():
        return [replace(s, text=s.text.upper()) for s in out]  # ՍՊԱՍՈՒՄ: its schwas too
    if out and original[:1].isupper() and syllables[0][0].epenthetic:
        first = out[0].text
        fixed = "Ը" + first[1:2].lower() + first[2:]
        out[0] = Syllable(fixed, True, out[0].phones)
    return out


def _stress(syllables: list[list[Seg]]) -> int:
    for i, syl in enumerate(syllables):
        if any(s.stressed for s in syl):
            return i
    for i in range(len(syllables) - 1, -1, -1):
        if any(s.vowel and s.ph != "ə" for s in syllables[i]):
            return i
    return len(syllables) - 1


def override_error(word: str, value: str) -> str | None:
    """Why a [lexicon] entry cannot be used, or None: կայ-սը-րու-թյուն."""
    example = "like կայ-սը-րու-թյուն"
    if not all(is_armenian(ch) or ch in "-" + "".join(STRESS_MARKS) for ch in value):
        return f"{value!r} is not in Armenian letters: write its sung syllables, {example}"
    chunks = [c for c in value.split("-") if c]
    vowels = [sum(1 for s in segments(c) if s.vowel) for c in chunks]
    if len(chunks) == 1 and vowels[0] > 1:
        return f"{value!r} needs a hyphen between its sung syllables, {example}"
    if any(n != 1 for n in vowels):
        return f"{value!r} needs one vowel per syllable, ը included, {example}"

    def bare(text: str) -> str:  # և as the ե and վ it is drawn for: Ե-րե-վան is Երևան
        return normalize(text).replace("-", "").replace("ը", "").replace("և", "եվ")

    if bare(value) not in (bare(word), bare(reformed(word))):  # Աստուած as Աստ-ված
        return f"{value!r} spells a different word"
    return None


ARTICLE_SONORANTS = {"ɾ", "l", "n"}  # սերն, ջուրն, տունն; ռն and մն always split
ARTICLE_PREFERENCE = -0.05  # the short սերն, unless a count asks for սե-րըն


def _article_schwa(syllables: list[list[Seg]]) -> list[list[Seg]] | None:
    """սերն, տունն: the article -ն after a sonorant, as սե-րըն with a schwa that
    may drop, as կյանքն's does (կյան-քըն, կյանք-նէ)."""
    last = syllables[-1] if syllables else []
    if len(last) < 3 or last[-1].ph != "n" or last[-2].ph not in ARTICLE_SONORANTS:
        return None
    if not last[-3].vowel and last[-3].ph != "j":  # ձայնն: ձայ-նըն, as տու-նըն
        return None
    return [*syllables[:-1], last[:-2], [last[-2], _schwa(), last[-1]]]


def _mark_hidden(syllables: list[list[Seg]], norm: str) -> None:
    """Mark the ը of a [lexicon] entry the word does not write as hidden: կայ-սը-րու-թյուն
    for կայսրություն, but not the ը of ըն-կեր."""
    k = 0
    for seg in (seg for syl in syllables for seg in syl):
        if not seg.src:
            continue
        if norm.startswith(seg.src, k):
            k += len(seg.src)
        elif seg.src == "ը":
            seg.epenthetic = True


def _from_override(spec: str) -> list[list[Seg]]:
    """A [lexicon] entry: syllables separated by "-", hidden ը written out."""
    syllables = []
    for chunk in spec.split("-"):
        segs = segments(chunk)
        if segs:
            syllables.append(segs)
    return syllables


# A noun's endings: its article, possessives, cases and plurals, which a [lexicon]
# entry for the noun carries over to (կայսրություն, կայսրությունը, -ում, -ները).
NOUN_ENDINGS = tuple(
    sorted(
        {
            *(
                stem + case
                for stem in ("", "ներ", "եր")
                for case in "ը ն ս դ ի ից ով ում ին".split()
            ),
            "ներ",
            "եր",
        },
        key=len,
        reverse=True,
    )
)


def _inflected_override(norm: str, overrides: dict[str, str]) -> list[list[Seg]] | None:
    """The syllables of a form of a [lexicon] word: the entry's, then the ending's
    (կայ-սը-րու-թյուն, կայ-սը-րու-թյու-նը)."""
    for ending in NOUN_ENDINGS:
        stem = norm[: -len(ending)]
        if not norm.endswith(ending) or stem not in overrides:
            continue
        segs = [seg for syl in _from_override(overrides[stem]) for seg in syl]
        segs += segments("ա" + ending)[1:]  # not word-initial: ով is [ov]
        return syllabify(segs, not stem_final(norm))
    return None


# Words that open a clause, so a ես after them is the pronoun: ու ես, որ ես.
# Not էլ (դու էլ ես: you too are) nor երբ (ե՞րբ ես գալու): a verb of I in the
# clause tells the pronoun after them (հետո էլ ես գնացի, երբ ես եկա).
CLAUSE_OPENERS = set("ու և եվ բայց իսկ որ թե եթե քանի մինչ ապա հետո".split())
# After a negation, an or, or a focus word, ես is I: ոչ ես, կամ ես, նույնիսկ ես.
BEFORE_PRONOUN = set("ոչ կամ նաև նաեւ նույնիսկ անգամ հենց միայն թեկուզ".split())
FIRST_PERSON = {"եմ", "չեմ", "էի", "չէի"}
# 1st person aorists that do not end in -ցի: տեսա, եկա (I saw, I came).
FIRST_AORISTS = set(
    "տեսա եկա եղա դարձա մեռա կորա հասա մտա ելա կերա տարա առա գտա դրի թողի բերի տվի".split()
)
# Words that end like a verb of I but are none: անգամ (time), դեմ (against), կամ (or).
NOT_VERBS = {"անգամ", "դեմ", "կամ", "համ"}


def _verb_of_i(norm: str) -> bool:
    if norm in NOT_VERBS:
        return False
    if norm in FIRST_PERSON or norm in FIRST_AORISTS or norm.endswith(("եմ", "ամ", "ցի")):
        return True
    # չեկա, չեղա; and the conditional or past of I behind կ- or չ-: կգայի, կսիրեի
    return norm[:1] in "կչ" and (norm[1:] in FIRST_AORISTS or norm.endswith(("այի", "եի")))


def auxiliary_es(norms: list[str], i: int, clause_end: list[bool]) -> bool:
    """Whether the ես at i is the auxiliary (you are, [es]) leaning on the word
    before it, not the pronoun I ([jes]). The pronoun opens its clause (Ես եմ,
    ու ես, ..., ես), follows an auxiliary of I (սիրում եմ ես, ով եմ ես) or comes
    with a verb of I before or after it in its clause (հիմա ես գիտեմ, քեզ ես
    սիրեցի, երեկ ես տեսա, կերգեմ ես, մի օր ես կգայի); the auxiliary
    follows its word (գալիս ես, ինչու ես լռում, իմ սերն ես, գեղեցիկ ես ամեն անգամ),
    and ends its clause after one (ուր ես, ես կգամ)."""
    if i == 0 or clause_end[i - 1] or norms[i - 1] in CLAUSE_OPENERS | BEFORE_PRONOUN:
        return False
    for k in range(i - 1, -1, -1):  # կերգեմ ես, սիրում եմ քեզ ես: a verb of I before
        if _verb_of_i(norms[k]):
            return False
        if k == 0 or clause_end[k - 1] or norms[k] in CLAUSE_OPENERS:
            break
    if clause_end[i]:
        return True  # ուր ես, ...: a verb of I in a later clause is another's
    for k in range(i + 1, len(norms)):
        if _verb_of_i(norms[k]):
            return False
        if clause_end[k]:
            break
    return True


def read_es(word: Word, auxiliary: bool) -> None:
    """Make a ես the auxiliary [es], an enclitic, or the pronoun [jes], a word."""
    if auxiliary:
        word.readings = tuple(
            replace(r, phones=r.phones[1:]) if r.phones[:1] == ("j",) else r for r in word.readings
        )
        first = word.syllables[0] if word.syllables else None
        if first is not None and first.text[:1] in "yY" and word.text[:1] not in "yY":
            # es typed in Latin, shown from its sounds: the auxiliary has no y
            word.syllables = (replace(first, text=first.text[1:]), *word.syllables[1:])
    else:
        word.enclitic = word.clitic = False
        word.readings = tuple(
            replace(r, stress=0, source="rule") if r.stress is None else r for r in word.readings
        )


# Endings of a finite verb, a participle or an infinitive, after the negative չ- or
# the future կ-: չգնաս, կգնամ, չգցել.
VERB_ENDINGS = tuple(
    sorted(
        "ել ալ եմ ես ենք եք են ամ աս անք աք ան ի իր ինք իք ին եի եիր եր եինք եիք եին ա "
        "ացի եցի ում ած այի այիր ար այինք այիք ային "
        "աց եց ավ ացիր եցիր ացինք եցինք ացիք եցիք ացին եցին ալու ելու".split(),
        key=len,
        reverse=True,
    )
)
NOT_PREFIXED = ("չնչին", "կծծի")  # roots that only look like չ- or կ- and a verb


def _stem_schwas(norm: str, segs: list[Seg]) -> list[int]:
    """Where a word keeps schwas its sounds alone would not give it: after the
    negative չ- or the future կ- before a stem that opens on two consonants
    (չը-գը-նամ, կը-գը-նամ, as գը-նալ) or on a consonant, a stop and another
    (կը-գըտ-նեմ, as գըտ-նել), and in a reduplicated root (բըլ-բը-լալ)."""
    if len(segs) < 5 or any(s.vowel for s in segs[:4]):
        return [] if len(segs) < 4 or any(s.vowel for s in segs[:3]) else _prefixed(norm, segs)
    same = [s.ph.replace("ɾ", "r") for s in segs[:4]]  # թրթռ- repeats with ր and ռ
    if same[0] == same[2] and same[1] == same[3]:
        return [1, 3]
    if segs[4].vowel and is_stop(segs[2].ph) and norm[:1] in "չկ":
        return _prefixed(norm, segs)
    return []


def _prefixed(norm: str, segs: list[Seg]) -> list[int]:
    long_stem = not segs[3].vowel and len(segs) > 4 and segs[4].vowel and is_stop(segs[2].ph)
    if not (segs[3].vowel or long_stem) or norm.startswith(NOT_PREFIXED):
        return []
    if segs[1].ph in PROTHESIS_FIRST and is_stop(segs[2].ph):
        return []  # չ- before ըս-պա-սել: the prothesis stays
    stem = norm[1:]
    ending = next((e for e in VERB_ENDINGS if stem.endswith(e) and len(stem) > len(e) + 1), None)
    if ending is None:
        return []
    if norm[0] == "չ":
        return [1, 2]
    # The future is կ- and a subjunctive whose ending matches its verb's conjugation:
    # կգնամ, կգնա of գնալ, կքնեմ, կքնի of քնել; not a root like կթխա or կշռել.
    base = stem[: -len(ending)]
    for infinitive, endings in FUTURE_ENDINGS:
        verb = base + infinitive
        if ending in endings and (verb in cluster_roots() or verb in FUTURE_VERBS):
            return [1, 2]
    return []


# Verbs that open on two consonants with a schwa between which the compound roots
# leave out (they would break a compound), so the future still knows them: կգրեմ.
FUTURE_VERBS = frozenset({"գրել", "կրել", "գտնել", "մտնել", "կտրել", "կպնել"})


FUTURE_ENDINGS = (
    ("ալ", set("ամ աս ա անք աք ան այի այիր ար այինք այիք ային".split())),
    ("ել", set("եմ ես ի ենք եք են եի եիր եր եինք եիք եին".split())),
)


# A voiced stop after ր is said voiceless and aspirated: երգ [jɛɾkʰ], մարդ [mɑɾtʰ],
# so երգ rhymes with բերք. The affricates keep their letter's sound here, as
# verse rhymes them (մեջ / վերջ).
AFTER_R = {"b": "pʰ", "g": "kʰ", "d": "tʰ"}


def _after_r(phones: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        AFTER_R.get(ph, ph) if k and phones[k - 1] == "ɾ" else ph for k, ph in enumerate(phones)
    )


# Armenian typed in Latin letters, as chats and Suno prompts write it: longest
# spellings first. ե opens a word as ye, ո as vo; elsewhere e and o.
FROM_LATIN = (
    ("tch", "ճ"), ("dzh", "ջ"), ("ch'", "չ"), ("ts'", "ց"), ("t'", "թ"), ("p'", "փ"),
    ("k'", "ք"), ("sh", "շ"), ("ch", "չ"), ("zh", "ժ"), ("kh", "խ"), ("gh", "ղ"),
    ("ts", "ց"), ("dz", "ձ"), ("rr", "ռ"), ("th", "թ"), ("ph", "փ"), ("ou", "ու"),
    ("ev", "և"), ("u", "ու"), ("a", "ա"), ("b", "բ"), ("g", "գ"), ("d", "դ"),
    ("e", "ե"), ("z", "զ"), ("i", "ի"), ("l", "լ"), ("x", "խ"), ("k", "կ"),
    ("h", "հ"), ("m", "մ"), ("n", "ն"), ("o", "ո"), ("p", "պ"), ("j", "ջ"),
    ("r", "ր"), ("s", "ս"), ("v", "վ"), ("t", "տ"), ("c", "ց"), ("q", "ք"),
    ("f", "ֆ"), ("w", "վ"), ("@", "ը"), ("ə", "ը"),
)  # fmt: skip
LATIN_VOWELS = set("aeiouəy")


# The auxiliaries as Latin typing spells them, with the e that is ե.
LATIN_AUXILIARIES = {"em": "եմ", "es": "ես", "enq": "ենք", "eq": "եք", "en": "են"}


def from_latin(word: str) -> str:
    """Latin-letter Armenian in Armenian letters: mtnem մտնեմ, kyanq կյանք, vor որ,
    yes ես, Yerevan Երևան. y is յ after or before a vowel and ը between
    consonants (ynker ընկեր)."""
    low = word.lower().replace("’", "'")
    if low in ("ev", "yev"):
        return "և"
    if low in LATIN_AUXILIARIES:  # sirum em: the auxiliary եմ, not էմ
        return LATIN_AUXILIARIES[low]
    out, k = [], 0
    if low.startswith("ye"):
        out, k = ["ե"], 2
    elif low.startswith("vo") and low[2:3] not in LATIN_VOWELS:
        out, k = ["ո"], 2
    elif low.startswith("e"):
        out, k = ["է"], 1
    elif low.startswith("o"):
        out, k = ["օ"], 1
    while k < len(low):
        ch = low[k]
        if ch == "y":
            near_vowel = low[k - 1 : k] in LATIN_VOWELS or low[k + 1 : k + 2] in LATIN_VOWELS
            out.append("յ" if near_vowel and k else "ը" if not near_vowel else "յ")
            k += 1
            continue
        for latin, armenian in FROM_LATIN:
            if low.startswith(latin, k):
                if latin == "ev" and k + 2 < len(low) and low[k + 2] in LATIN_VOWELS:
                    continue  # եվ before a vowel: Եվրոպա
                out.append(armenian)
                k += len(latin)
                break
        else:
            k += 1  # an apostrophe or a letter Armenian has no use for
    return "".join(out)


# Abbreviations are said letter by letter: a vowel as itself, Հ and Կ with ա,
# any other consonant with ե: ԱՄՆ Ա-Մե-Նե, ԵՊՀ Ե-Պե-Հա, ՀՀ Հա-Հա.
LETTER_VOWELS = {
    "ա": ("a",),
    "ե": ("j", "e"),
    "է": ("e",),
    "ը": ("ə",),
    "ի": ("i",),
    "ո": ("v", "o"),
    "օ": ("o",),
}


def _letter_name(ch: str) -> list[Seg]:
    low = ch.lower()
    if low in LETTER_VOWELS:
        *glide, vowel = LETTER_VOWELS[low]
        return [Seg(g, "", False) for g in glide] + [Seg(vowel, ch, True)]
    vowel = "ա" if low in "հկ" else "ե"
    return [Seg(LETTERS[low], ch, False), Seg("a" if vowel == "ա" else "e", vowel, True)]


def _case_ending(ending: str, after: str) -> list[Seg]:
    """The segments of a case ending after a letter's name: ից, ի, ն, ում, with the
    յ said between ա or օ and a vowel (ՀՀ-ի, Հա-Հա-յի)."""
    segs = segments("ա" + ending)[1:]  # not word-initial: ով is [ov], not [vov]
    if segs and segs[0].vowel and after in ("a", "o"):
        segs.insert(0, Seg("j", "յ", False))
    return segs


def abbreviation(token: str, capitals: bool = False) -> Word | None:
    """An abbreviation in capitals with no vowel letter, or one in at most three
    letters, sung letter by letter and stressed on the last (ՀՀ, ԵՊՀ, ԱՄՆ); ՀԱՊԿ and
    ՆԱՏՕ are words. In a line written all in capitals only one with no vowel letter
    is spelt. A case ending after a hyphen is said after the letters and takes the
    stress (ԱՄՆ-ից, Ա-Մե-Նե-ից; ՀՀ-ի, Հա-Հա-յի)."""
    head, hyphen, ending = token.partition("-")
    if not 2 <= len(head) <= 5 or not head.isupper():
        return None
    if hyphen and not (
        1 <= len(ending) <= 4 and ending.islower() and all(is_armenian(ch) for ch in ending)
    ):
        return None
    low = head.lower()
    if not all(ch in LETTERS or ch in LETTER_VOWELS for ch in low):
        return None
    if low in ("եվ", "եւ"):
        return None  # ԵՎ: և, which has no capital of its own
    if ("ու" in low or low in short_words()) and not hyphen:
        return None  # ԴՈՒ, ՔԵԶ, ԻՆՁ: a word written in capitals for emphasis (but ԵՄ-ում)
    vowels = sum(ch in LETTER_VOWELS for ch in low)
    if vowels and (capitals or vowels > 1 or len(low) > 3):
        return None
    segs = [seg for ch in head for seg in _letter_name(ch)]
    if ending:
        segs += _case_ending(ending, segs[-1].ph)
    syllables = syllabify(segs, possessive=False)
    stress = _stress(syllables)
    return Word(
        text=token,
        norm=token.lower(),
        lang=CODE,
        syllables=tuple(_display(syllables, token, caps=False)),  # Հա-Հա: letter names
        readings=(Reading(stress, tuple(s.ph for s in segs), token.lower(), "lexicon"),),
        spelled=True,
    )


# Classical spellings the 1922 reform replaced, read as their reformed ones, in
# order: ու before a vowel is վ (Աստուած, արուեստ: OU_VOWEL); եաւ is և (սեաւ); a
# final իւ is իվ (թիւ, հաշիւ), any other իւ յու (ձիւն, իւր); յեա and եա before a classical
# ending are յա (հայեացք, կեանք, անցեալ, Թումանեան, ուրախութեամբ, մանեակ); ոյ
# before a consonant is ույ (լոյս); a polysyllable's final -այ or -ոյ drops its յ
# (հիմայ, հետոյ, and կայ); and then a յ that opens the word is հ (յոյս, յետոյ).
# Never a loan's: եա before another consonant or an ending (սեանս, Կորեայում,
# ռեալ), ոյ before ֆ (բոյֆրենդ), ու before a vowel in a loan (դուետ), a final ոյ
# of one syllable (Նոյ), or a name's (Նիկոլայ, Տոլստոյ).
_C = "բգդզթժլխծկհձղճմյնշչպջռսվտրցփք"
CLASSICAL = (
    (re.compile("եաւ"), "և"),
    (re.compile("իւ$"), "իվ"),
    (re.compile("իւ"), "յու"),
    (re.compile("յեա(?=[" + _C + "])"), "յա"),
    (re.compile("եա(?=ն(?:$|[քցիըեաո])|լ(?:$|ի|ն|ը)|կ(?:$|ը|ն|ի)|մբ|ց|յ(?:$|[" + _C + "]))"), "յա"),
    (re.compile("ոյ(?=[^\u0561-\u0587]*[" + _C + "])"), "ույ"),
)
FINAL_YOD = re.compile("(?<=[աո])յ$")  # հիմայ, հետոյ: the յ unsung, so unwritten
LOAN_CLASSICAL = ("ռեալ", "իդեալ", "դուետ", "սիլուետ", "լուիզ", "ռուանդ", "կորեա", "սեանս")
# Common classical forms with a final silent յ, whose reformed spelling drops it; a
# reformed word may end in -այ too (ամերիկահայ, դերբայ, սամուրայ), so another word
# drops it only beside another classical sign.
FINAL_YOD_WORDS = {
    **{w: w[:-1] for w in "կայ չկայ հիմայ վրայ տղայ ապագայ հետոյ աստծոյ".split()},
    "աստուծոյ": "աստծո", "յետոյ": "հետո",
}  # fmt: skip
# ու before a vowel is վ in a classical stem (Աստուած, արուեստ, տուի), or beside
# another classical sign; not in a reformed word or a name (այնուամենայնիվ, Էդուարդ).
OU_VOWEL = re.compile("(?<=[" + _C + "])ու(?=[աեէիո])")
OU_STEMS = ("աստուած", "արուեստ", "տուի", "տուեց", "տուել", "տուող")


def reformed(token: str) -> str:
    """token in the reformed spelling, its letter case kept: կեանք as կյանք."""
    low = token.lower()
    if low.startswith(LOAN_CLASSICAL) or "ֆ" in low:
        return token
    new = FINAL_YOD_WORDS.get(low, low)
    for pattern, repl in CLASSICAL:
        new = pattern.sub(repl, new)
    classical = new != low  # a sign the word is in the old spelling
    if low.startswith(OU_STEMS) or (classical and not token[:1].isupper()):
        new = OU_VOWEL.sub("վ", new)
    vowels = sum(seg.vowel for seg in segments(new))
    if classical and vowels > 1 and not token[:1].isupper() and FINAL_YOD.search(new):
        new = FINAL_YOD.sub("", new)  # յոյսայ, but մակբայ, Նիկոլայ, Տոլստոյ
    if new != low and new[:1] == "յ" and new[1:2] in "աեէիոու":
        new = "հ" + new[1:]  # յոյս, յետոյ: with another classical sign, a յ that opens is հ
    if new == low:
        return token
    if len(token) > 1 and token.isupper():
        return new.upper()
    return new[:1].upper() + new[1:] if token[:1].isupper() else new


def analyze_word(
    token: str, overrides: dict[str, str] | None = None, capitals: bool = False
) -> Word:
    modern = reformed(token)
    if modern != token and not (overrides or {}).get(normalize(token)):
        word = analyze_word(modern, overrides, capitals)  # կեանք: classical spelling
        word.text = token
        word.notes.append(f"classical spelling, read as {modern}")
        return word
    norm = normalize(token)
    if not (overrides or {}).get(norm):
        spelled = abbreviation(token, capitals)
        if spelled is not None:
            return spelled
    if lyrics.held_note(norm, "աեէըիոօ"):  # Օօօ: one held note
        word = analyze_word(token[0], overrides, capitals)
        if word.clitic or word.enclitic:  # աաա is sung, not the auxiliary ա
            phones = word.readings[0].phones if word.readings else ()
            word.readings = (Reading(0, phones, norm, "rule"),)
            word.clitic = word.enclitic = False
        word.text, word.norm, word.held = token, norm, True
        word.syllables = tuple(replace(s, text=token) for s in word.syllables)
        return word
    override = (overrides or {}).get(norm)
    inflected = None if override else _inflected_override(norm, overrides or {})
    optional, prefer_short = None, False
    if override or inflected:
        syllables = _from_override(override) if override else inflected or []
        _mark_hidden(syllables, norm)
        source = "user"
    else:
        segs = segments(token)
        for i in reversed(_stem_schwas(norm, segs)):
            segs.insert(i, _schwa())
        inserted = []
        for i in compound_points(norm):
            inserted.append(_schwa())
            segs.insert(i, inserted[-1])
        syllables = syllabify(segs, not stem_final(norm))
        source = "rule"
        optional = next(
            (k for k, syl in enumerate(syllables) if any(s is t for s in syl for t in inserted)),
            None,
        )
        article = _article_schwa(syllables)
        if article is not None and optional is None:
            syllables, optional, prefer_short = article, len(article) - 1, True
    shown = _display(syllables, token)
    if source == "user" and len(token) > 1 and token.isupper():  # ԿԱՅՍԸՐՈՒԹՅՈՒՆ
        shown = [replace(s, text=s.text.upper()) for s in shown]
    elif source == "user" and token[:1].isupper() and shown:  # Կայսրություն as written
        shown[0] = replace(shown[0], text=shown[0].text[:1].upper() + shown[0].text[1:])
    phones = _after_r(tuple(s.ph for syl in syllables for s in syl))
    clitic = norm in CLITICS
    stress = None if clitic and len(syllables) > 1 else _stress(syllables)
    if any(s.stressed for syl in syllables for s in syl):
        source = "mark"
        stress = _stress(syllables)
        clitic = False
    reading = Reading(stress, phones, norm, "clitic" if stress is None else source)
    first = syllables[0] if syllables else []
    last = syllables[-1] if syllables else []
    linkable = len(last) == 3 and last[1].epenthetic and not last[2].vowel
    return Word(
        text=token,
        norm=norm,
        lang=CODE,
        syllables=tuple(shown),
        readings=(reading,),
        weak=clitic or len(syllables) == 1,
        clitic=clitic,
        enclitic=norm in AUXILIARIES,
        head_schwa=len(syllables) > 1 and bool(first) and first[0].ph == "ə",
        tail_schwa=len(syllables) > 1 and linkable,
        drop=optional,
        optional=optional,
        drop_cost=ARTICLE_PREFERENCE if prefer_short else 0.0,
        optional_why=(
            "the article -ն is sung with or without its ը"
            if prefer_short
            else "speech often leaves out the ը of a compound's second root"
            if optional is not None
            else ""
        ),
    )
