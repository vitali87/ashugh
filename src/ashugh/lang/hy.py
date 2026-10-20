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

from dataclasses import dataclass
from functools import cache
from importlib import resources

from ..model import Reading, Syllable, Word
from ..phon import is_obstruent, is_stop, sonority

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
AUXILIARIES = {"եմ", "ես", "է", "ենք", "եք", "են", "էի", "էիր", "էր", "էինք", "էիք", "էին"}
CLITICS = AUXILIARIES | {"ու", "և", "եւ", "եվ", "էլ", "թե", "որ", "մի", "ի"}  # Եվ opens a sentence

PROTHESIS_FIRST = {"s", "z", "ʃ"}
MAX_CODA = 2
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
# Final clusters Wiktionary splits with a schwa in 19 of 21 dictionary forms.
FINAL_SPLIT = {("m", "n"), ("r", "n")}
NOT_POSSESSIVE = {
    "չորս", "ներս", "դուրս", "որս", "ձկնորս", "թարս", "կարս", "կուրս", "մարս", "ֆարս",
    "ռեսուրս", "կոնկուրս", "դիսկուրս", "շանս", "բալանս", "ռոմանս", "ֆինանս", "սեանս",
    "ավանս", "նյուանս", "դիստանս", "ռեվերանս", "ալյանս", "վալս", "պուլս", "ֆոնդ",
    "բրենդ", "լեգենդ", "տրենդ", "բանդ", "սթենդ", "հարս", "վարս", "պարս", "ռեզոնանս",
    "կոնֆերանս", "ռենեսանս", "ծնունդ", "սերունդ", "գունդ", "հունդ", "փունդ", "խանդ",
    "ընդ", "դիվիդենդ", "պոնդ", "հոլանդ",
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
            for seg in reversed(segs):
                if seg.vowel:
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


def _valid_coda(cs: list[Seg], final: bool, possessive: bool = True) -> bool:
    if len(cs) > MAX_CODA:
        return False
    if len(cs) == 2:
        a, b = cs[0].ph, cs[1].ph
        if final and (a, b) in FINAL_SPLIT:
            return False
        if sonority(a) < sonority(b) and not (final and not possessive and b == "s"):
            return False  # a stem may end in a stop and ս: մաքս, բոքս
        if final and possessive and _possessive(a, b):
            return False
    return True


def _possessive(a: str, b: str) -> bool:
    """Whether a final consonant pair reads as a stem plus the possessive ս or դ."""
    return b in ("s", "d") and (is_obstruent(a) or a in POSSESSIVE_AFTER)


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


def compound_points(norm: str) -> list[int]:
    """Segment indices to put a compound's schwa before, last first."""
    keys = compound_schwas()
    found = (norm[:k] for k in range(MIN_COMPOUND, len(norm) + 1) if norm[:k] in keys)
    return sorted({len(segments(key)) - 1 for key in found}, reverse=True)


def stem_final(norm: str) -> bool:
    """Whether a final ս or դ of norm is the stem's own rather than the possessive."""
    if norm in POSSESSIVE_FORMS:
        return False
    words = lexical_endings()
    if norm in words or any(norm.endswith(s) and len(norm) >= n for s, n in LEXICAL_SUFFIXES):
        return True
    return any(
        norm[k:] in words for k in range(MIN_HEAD, len(norm) - 2) if norm[k - 1 : k] in LINKERS
    )


def _onsets(cs: list[Seg]) -> list[int]:
    """Possible onset lengths for the vowel after cluster cs."""
    if not cs:
        return [0]
    options = [1]
    if len(cs) >= 2 and cs[-1].ph == "j" and cs[-2].ph != "j":
        options.append(2)
    return options


def _schwa_runs(
    cs: list[Seg], closed_last: bool, possessive: bool = True
) -> list[list[tuple[list[Seg], list[Seg]]]]:
    """Every way to cut cs into schwa syllables (onset, coda)."""
    if not cs:
        return [[]]
    runs = []
    for coda_len in range(0, MAX_CODA + 1):
        if 1 + coda_len > len(cs):
            break
        rest = len(cs) - 1 - coda_len
        onset = cs[rest : rest + 1]
        coda = cs[rest + 1 :]
        if closed_last and not coda:
            continue
        if not _valid_coda(coda, final=closed_last, possessive=possessive):
            continue
        for head in _schwa_runs(cs[:rest], closed_last=False):
            runs.append(head + [(onset, coda)])
    return runs


def _parse_cluster(cs: list[Seg], has_prev: bool, has_next: bool, possessive: bool = True):
    """Split a consonant cluster into (coda, schwa syllables, onset)."""
    best = None
    for onset_len in _onsets(cs) if has_next else [0]:
        onset = cs[len(cs) - onset_len :] if onset_len else []
        inner = cs[: len(cs) - onset_len]
        coda_lens = range(0, min(MAX_CODA, len(inner)) + 1) if has_prev else [0]
        for coda_len in coda_lens:
            coda = inner[:coda_len]
            final = not has_next
            if has_prev and not _valid_coda(coda, final, possessive=possessive):
                continue
            middle = inner[coda_len:]
            for run in _schwa_runs(middle, not has_next, possessive=possessive):
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


def syllabify(segs: list[Seg], possessive: bool = True) -> list[list[Seg]]:
    vowels = [i for i, s in enumerate(segs) if s.vowel]
    if not vowels:
        # No vowel letter at all: one schwa after the first consonant.
        return [segs[:1] + [_schwa()] + segs[1:]] if segs else []

    syllables: list[list[Seg]] = []
    lead = segs[: vowels[0]]
    # Prothesis: ս/զ/շ + stop at the start of the word.
    while len(lead) >= 2 and lead[0].ph in PROTHESIS_FIRST and is_stop(lead[1].ph):
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


def _display(syllables: list[list[Seg]], original: str) -> list[Syllable]:
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
    if normalize(value).replace("-", "").replace("ը", "") != normalize(word).replace("ը", ""):
        return f"{value!r} spells a different word"
    return None


def _from_override(spec: str) -> list[list[Seg]]:
    """A [lexicon] entry: syllables separated by "-", hidden ը written out."""
    syllables = []
    for chunk in spec.split("-"):
        segs = segments(chunk)
        if segs:
            syllables.append(segs)
    return syllables


def analyze_word(token: str, overrides: dict[str, str] | None = None) -> Word:
    norm = normalize(token)
    override = (overrides or {}).get(norm)
    optional = None
    if override:
        syllables = _from_override(override)
        source = "user"
    else:
        segs = segments(token)
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
    shown = _display(syllables, token)
    phones = tuple(s.ph for syl in syllables for s in syl)
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
    )
