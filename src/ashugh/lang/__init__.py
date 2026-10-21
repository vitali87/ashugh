"""Language registry and script detection."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import replace
from types import ModuleType

from .. import lyrics
from ..model import Reading, Syllable, Word
from ..phon import is_vowel
from . import en, hy, ru

ANALYZERS: dict[str, ModuleType] = {"hy": hy, "ru": ru, "en": en}
NAMES = {"hy": "Armenian", "ru": "Russian", "en": "English", "xx": "unsupported script"}


AMPERSAND = {"en": "and", "ru": "и", "hy": "և"}


def analyze_word_as(token: str, lexicon: dict[str, str]) -> Word:
    """One word by its own script's analyzer."""
    script = script_of(token)
    return (
        ANALYZERS[script].analyze_word(token, lexicon)
        if script in ANALYZERS
        else foreign_word(token)
    )


def script_of(token: str) -> str:
    for ch in token:
        if hy.is_armenian(ch):
            return "hy"
        if ru.is_cyrillic(ch):
            return "ru"
        if en.is_latin(ch):
            return "en"
        if ch.isalpha():
            return "xx"
    return ""


def override_error(word: str, value: str) -> str | None:
    """Why a [lexicon] entry cannot be used, by the script of its word; None if
    it can, or if no analyzer reads that script."""
    module = ANALYZERS.get(script_of(word))
    return module.override_error(word, value) if module else None


def detect(tokens: list[str]) -> str:
    counts: dict[str, int] = {}
    for t in tokens:
        s = hy.CODE if LATIN_WITH_ENDING.fullmatch(t) else script_of(t)  # TikTok-ում
        if s and s != "xx":
            counts[s] = counts.get(s, 0) + 1
    if not counts:
        return "xx" if any(script_of(t) == "xx" for t in tokens) else ""
    return max(counts, key=lambda k: counts[k])


# Vowel letters of scripts ashugh does not analyze, by their base letter: Latin
# (with any accent), Greek, Georgian.
FOREIGN_VOWELS = frozenset("aeiouyæøœαεηιοωυაეიოუ")


def _vowel_groups(norm: str) -> list[re.Match]:
    marks = "".join(
        "v" if unicodedata.normalize("NFD", ch)[:1] in FOREIGN_VOWELS else "c" for ch in norm
    )
    return list(re.finditer("v+", marks))


def foreign_word(token: str) -> Word:
    """A rough vowel-group count for a word in a script ashugh does not analyze."""
    norm = token.lower()
    groups = _vowel_groups(norm)
    if len(groups) > 1 and norm.endswith("e") and not norm.endswith(("le", "ee")):
        groups = groups[:-1]
    n = max(1, len(groups))
    cuts = [g.start() - (g.start() > 0 and token[g.start() - 1].isalpha()) for g in groups[1:n]]
    pieces = [token[a:b].strip("-") for a, b in zip([0, *cuts], [*cuts, len(token)])]
    syllables = tuple(Syllable(p) for p in pieces)
    phones = tuple(["a"] * n)
    readings = tuple(Reading(p, phones, norm, "guess") for p in range(n))
    return Word(
        token, norm, "xx", syllables, readings, weak=True, notes=["no analyzer for this script"]
    )


PHRASE_END = re.compile(r"\s*[,.;:!?…—–։՝]")
SENTENCE_END = re.compile(r"\s*[.!?…]")


def _sentence_starts(tokens: list[str], text: str | None) -> list[bool]:
    """Which tokens open a sentence: the first, and any after . ! ? or …"""
    starts = [k == 0 for k in range(len(tokens))]
    if text is not None:
        spans = lyrics.token_spans(text)
        for k, (_, stop, _) in enumerate(spans[: len(tokens) - 1]):
            if SENTENCE_END.match(text, stop):
                starts[k + 1] = True
    return starts


def analyze(
    lang: str, tokens: list[str], lexicon: dict[str, str], text: str | None = None
) -> list[Word]:
    """Words of one line; tokens in another script than lang get their own analyzer.
    With the line's text, a preposition before a comma or full stop is stressed
    like one at the end of the line: hold on, hold on."""
    words: list[Word] = []
    letters = "".join(ch for t in tokens for ch in t if ch.isalpha())
    capitals = len(letters) > 3 and letters.isupper()  # I AM HERE: am, not A.M.
    in_latin = lang == hy.CODE and latin_armenian(tokens)
    for token in tokens:
        if LATIN_WITH_ENDING.fullmatch(token) and (lang == hy.CODE or in_latin):
            words.append(_latin_with_ending(token, lexicon))
            continue
        if in_latin and script_of(token) == en.CODE:
            words.append(_from_latin(token, lexicon))
            continue
        if token == "&":  # rock & roll: the line's own and
            and_ = analyze_word_as(AMPERSAND.get(lang, "and"), lexicon)
            and_.text = token
            words.append(and_)
            continue
        script = script_of(token)
        if script == en.CODE:
            words.append(en.analyze_word(token, lexicon, capitals))
        elif script == ru.CODE:
            words.append(ru.analyze_word(token, lexicon, capitals))
        elif script == hy.CODE:
            words.append(hy.analyze_word(token, lexicon, capitals))
        elif script in ANALYZERS:
            words.append(ANALYZERS[script].analyze_word(token, lexicon))
        else:
            words.append(foreign_word(token))
    if lang == "hy" or any(w.lang == "hy" for w in words):
        _armenian_elision(words)
    if any(w.lang == "ru" for w in words):
        ru.prefer_names(words, _sentence_starts(tokens, text))
        ru.vocables(words)
        ru.after_prepositions(words)
        ru.after_genitive(words)
        ru.second_locatives(words)
        ru.marked_leans(words)
        ru.ne_with_pronoun(words)
        ru.prepositions_in_o(words)
        ru.preposition_shift(words)
    if any(w.lang == "en" for w in words):
        en.heteronyms(words)
    end = words[-1] if words else None
    if end is not None and end.lang == "en" and end.clitic and end.norm not in ("a", "an", "the"):
        end.clitic = False  # a stranded preposition is stressed: gone by, roll in
    before = words[-2] if len(words) > 1 else None
    if end is not None and before is not None and end.lang == before.lang == "en":
        host = not (before.clitic or before.norm in en.WEAK or before.norm in en.COPULAS)
        if end.norm in en.OBJECTS and host:
            # need it, hold me, missing yóu on a beat; but all I want is yóu
            end.enclitic = end.free_end = True
        content = words[-3] if len(words) > 2 else None
        if end.norm in en.UNSTRESSED_OBJECTS and before.norm in en.PREPOSITIONS:
            # put a ring ón it, I'm ón it: the preposition takes the stress and the
            # rhyme, and it, which is all but never stressed, leans on it
            before.clitic = before.weak = False
            end.enclitic, end.free_end = True, False
        elif (
            end.norm in en.OBJECTS
            and before.norm in en.PREPOSITIONS
            and content is not None
            and content.lang == "en"
            and not (content.clitic or content.norm in en.WEAK)
        ):
            end.enclitic = end.free_end = True  # cáll to me; or back to mé on a beat
    ends = [False] * len(words)
    if text is not None:
        spans = lyrics.token_spans(text)
        for k, (w, (_, stop, _)) in enumerate(zip(words, spans)):
            ends[k] = bool(PHRASE_END.match(text, stop))
            if w.lang == "en" and w.norm in en.PARTICLES and ends[k]:
                w.clitic = False
    if ends:
        ends[-1] = True
    norms = [w.norm for w in words]
    for k, w in enumerate(words):
        if w.lang == "hy" and w.norm == "ես":
            hy.read_es(w, hy.auxiliary_es(norms, k, ends))
    return words


def _armenian_elision(words: list[Word]) -> None:
    """Mark the schwas that connected speech drops: a vowel before swallows a
    word's leading ը (նա ստացավ -> նաս-տա-ցավ), and a word's final schwa
    syllable links its consonant onto a vowel after it (կյանքն է -> կյանք-նէ).
    Elsewhere, a compound's inner schwa may drop (լու-սան-կար)."""

    def first(w: Word) -> str:
        return w.readings[0].phones[0] if w.readings and w.readings[0].phones else ""

    def last(w: Word) -> str:
        return w.readings[0].phones[-1] if w.readings and w.readings[0].phones else ""

    for i, w in enumerate(words):
        if w.lang != "hy":
            continue
        w.drop = w.optional
        head = w.head_schwa and i > 0 and is_vowel(last(words[i - 1]))
        tail = w.tail_schwa and i + 1 < len(words) and _vowel_initial(words[i + 1], first)
        if head and tail:
            # Both: speech swallows the leading ը outright and the final one may
            # link (քո ստվերն է: kʰos-tə-ver-ne).
            _swallow_head(w)
            w.drop = w.size - 1
        elif head:
            w.drop = 0
        elif tail:
            w.drop = w.size - 1


# The commonest English words: a Latin line of an Armenian song that has more of
# these than words English lacks is English (I love you, baby).
COMMON_ENGLISH = set(
    """the a an and or but if of to in on at by for with from up down out over about
    into is am are was were be been have has had do does did will would can could
    should i you he she it we they me him her us them my your his its our their this
    that what who where when why how all no not yes oh so just like love baby know
    want need go get got come say see make take give tell feel think time day night
    way one heart life world never always now here there then again back still only
    more ever every tonight dance dream""".split()
)
# Spellings English hardly has: q without u (kyanq), gh between vowels or before a
# consonant other than t (qaghaq, aghjik; not night), kh, zh, dz.
ARMENIAN_LATIN = re.compile(r"q(?!u)|[aeiou]gh[aeiou]|gh[^taeiou]|kh|zh|dz")


def latin_armenian(tokens: list[str]) -> bool:
    """A line of an Armenian song written in Latin letters (Mtnem aygin, qaghem
    vard) rather than an English line within it (I love you, baby): no Armenian
    letter, and more words English lacks or Armenian spells (q, gh, kh) than
    common English ones."""
    if any(script_of(t) == hy.CODE for t in tokens):
        return False
    latin = [t.lower() for t in tokens if script_of(t) == en.CODE]
    armenian = sum(1 for t in latin if ARMENIAN_LATIN.search(t) or not en.known(t))
    english = sum(1 for t in latin if t in COMMON_ENGLISH)
    return bool(latin) and armenian > english


def _from_latin(token: str, lexicon: dict[str, str]) -> Word:
    """A Latin-letter Armenian word, read in Armenian letters and shown in its own."""
    from ..suno import LATIN  # the same letters suno writes Armenian with

    w = hy.analyze_word(hy.from_latin(token), lexicon)
    w.text = token
    w.syllables = tuple(
        replace(s, text="".join(LATIN.get(ph, ph) for ph in s.phones)) for s in w.syllables
    )
    if token[:1].isupper() and w.syllables:
        first = w.syllables[0]
        w.syllables = (replace(first, text=first.text.capitalize()), *w.syllables[1:])
    return w


# A name in Latin letters with an Armenian case ending or article: TikTok-ում,
# Ararat-ը, iPhone-ս.
LATIN_WITH_ENDING = re.compile(r"([A-Za-z][A-Za-z'.]*)-([\u0561-\u0587]+)")


def _latin_with_ending(token: str, lexicon: dict[str, str]) -> Word:
    """A Latin name with an Armenian ending, an Armenian word: the name as English
    says it when it is English (TikTok, YouTube), else read in Armenian letters;
    the ending after it, a lone consonant taking a schwa after a consonant
    (iPhone-ս, -նըս); the stress on the ending's vowel, else on the name's end
    (TikTok-ու́մ, Ararát-ը)."""
    name, ending = token.split("-", 1)
    english = en.known(name.lower())
    head = en.analyze_word(name, lexicon) if english else _from_latin(name, lexicon)
    phones = head.readings[0].phones
    segs = hy.segments("ա" + ending)[1:]  # not word-initial: ով is [ov]
    tail: list[Syllable] = []
    syllables = list(head.syllables)
    if any(s.vowel for s in segs):
        for syl in hy.syllabify(segs, possessive=False):
            tail.append(Syllable("".join(s.src for s in syl), False, tuple(s.ph for s in syl)))
    elif phones and is_vowel(phones[-1]):  # Gucci-ն: a coda
        last = syllables[-1]
        syllables[-1] = replace(last, text=last.text + ending)
    else:  # iPhone-ս: ըս
        schwa = hy.Seg("ə", "ը", True, epenthetic=True)
        tail.append(Syllable("ը" + ending, True, ("ə", *(s.ph for s in segs))))
        segs = [schwa, *segs]
    full = [k for k, t in enumerate(tail) if any(is_vowel(p) and p != "ə" for p in t.phones)]
    stress = len(syllables) + full[-1] if full else len(syllables) - 1
    reading = Reading(stress, phones + tuple(s.ph for s in segs), token.lower(), "rule")
    return Word(token, token.lower(), hy.CODE, (*syllables, *tail), (reading,))


def _swallow_head(w: Word) -> None:
    """Drop a word's leading ը for good, its consonant joining the next syllable."""
    first, second, *rest = w.syllables
    joined = Syllable(
        first.text.replace("ը", "", 1).replace("Ը", "", 1) + second.text,
        second.epenthetic,
        first.phones[1:] + second.phones,
    )
    w.syllables = (joined, *rest)
    w.readings = tuple(
        replace(
            r,
            stress=None if r.stress is None else max(0, r.stress - 1),
            phones=r.phones[1:] if r.phones[:1] == ("ə",) else r.phones,
            secondary=tuple(max(0, k - 1) for k in r.secondary),
        )
        for r in w.readings
    )
    w.optional = None if w.optional is None else max(0, w.optional - 1)
    w.head_schwa = False


def _vowel_initial(w: Word, first) -> bool:
    # The auxiliary ես is [ɛs], not the pronoun [jɛs], when a linking -ն precedes it.
    return is_vowel(first(w)) or w.norm in hy.AUXILIARIES
