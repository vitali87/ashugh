"""Eastern Armenian: letters to phonemes, hidden-schwa epenthesis, syllables, stress.

Armenian writes almost none of its schwas. Մկրտիչ has one vowel letter and is
sung mə-kər-tich; սպասել is ըս-պա-սել. The rules this module applies:

* A word-initial ս, զ or շ before a stop or affricate takes a schwa in front of
  it (prothesis): սպասել -> ըս-պա-սել, ստվեր -> ըս-տը-վեր.
* Otherwise every consonant cluster is split into a coda for the vowel before
  it, an onset for the vowel after it, and as few schwa syllables as possible
  in between. An onset is one consonant, or a consonant plus յ (կյանք). A coda
  is at most two consonants that do not rise in sonority (սիրտ, միտք, but
  տետր -> տե-տըր, աստղ -> աս-տըղ).
* Word-final ս or դ after an obstruent is the possessive suffix and takes a
  schwa: սիրտս -> սիր-տըս, գլուխդ -> գը-լու-խըդ.
* Ties between equally short splits go to the longer onset (-թյուն), then to
  the split whose codas are longest reading from the right (Մկրտիչ ->
  մը-կըր-տիչ, Ադրբեջան -> ա-դըր-բե-ջան).

Stress falls on the last syllable whose vowel is not a schwa. The marks ՛ ՜ ՞
written after a vowel move it there.

Schwas that come from morphology rather than from the cluster (կայսրություն
keeps the schwa of կայսր) are out of reach of these rules; the spec's
[lexicon] table fixes them.
"""

from __future__ import annotations

from dataclasses import dataclass

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
CLITICS = AUXILIARIES | {"ու", "և", "եւ", "էլ", "թե", "որ", "մի", "ի"}

PROTHESIS_FIRST = {"s", "z", "ʃ"}
MAX_CODA = 2


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


def _valid_coda(cs: list[Seg], final: bool) -> bool:
    if len(cs) > MAX_CODA:
        return False
    if len(cs) == 2:
        a, b = cs[0].ph, cs[1].ph
        if sonority(a) < sonority(b):
            return False
        if final and b in ("s", "d") and is_obstruent(a):
            return False
    return True


def _onsets(cs: list[Seg]) -> list[int]:
    """Possible onset lengths for the vowel after cluster cs."""
    if not cs:
        return [0]
    options = [1]
    if len(cs) >= 2 and cs[-1].ph == "j" and cs[-2].ph != "j":
        options.append(2)
    return options


def _schwa_runs(cs: list[Seg], closed_last: bool) -> list[list[tuple[list[Seg], list[Seg]]]]:
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
        if not _valid_coda(coda, final=closed_last):
            continue
        for head in _schwa_runs(cs[:rest], closed_last=False):
            runs.append(head + [(onset, coda)])
    return runs


def _parse_cluster(cs: list[Seg], has_prev: bool, has_next: bool):
    """Split a consonant cluster into (coda, schwa syllables, onset)."""
    best = None
    for onset_len in _onsets(cs) if has_next else [0]:
        onset = cs[len(cs) - onset_len :] if onset_len else []
        inner = cs[: len(cs) - onset_len]
        coda_lens = range(0, min(MAX_CODA, len(inner)) + 1) if has_prev else [0]
        for coda_len in coda_lens:
            coda = inner[:coda_len]
            if has_prev and not _valid_coda(coda, final=not has_next):
                continue
            middle = inner[coda_len:]
            for run in _schwa_runs(middle, closed_last=not has_next):
                yod = sum(1 for o, _ in run if o[0].ph == "j")
                # Right to left, the longer coda wins: մը-կըր-տիչ, not մըկ-րը-տիչ.
                codas = tuple(-len(c) for _, c in reversed(run)) + (-coda_len,)
                score = (len(run), yod, -onset_len, codas)
                if best is None or score < best[0]:
                    best = (score, coda, run, onset)
    if best is None:
        return None
    return best[1], best[2], best[3]


def syllabify(segs: list[Seg]) -> list[list[Seg]]:
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
        parsed = _parse_cluster(cluster, has_prev=True, has_next=has_next)
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
        out.append(Syllable("".join(parts), any(s.epenthetic for s in syl)))
    if out and original[:1].isupper() and syllables[0][0].epenthetic:
        first = out[0].text
        fixed = "Ը" + first[1:2].lower() + first[2:]
        out[0] = Syllable(fixed, True)
    return out


def _stress(syllables: list[list[Seg]]) -> int:
    for i, syl in enumerate(syllables):
        if any(s.stressed for s in syl):
            return i
    for i in range(len(syllables) - 1, -1, -1):
        if any(s.vowel and s.ph != "ə" for s in syllables[i]):
            return i
    return len(syllables) - 1


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
    if override:
        syllables = _from_override(override)
        source = "user"
    else:
        syllables = syllabify(segments(token))
        source = "rule"
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
    )
