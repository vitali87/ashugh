"""Language registry and script detection."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import replace
from types import ModuleType

from .. import lyrics
from ..model import Reading, Syllable, Word, nuclei
from ..phon import adapt_english, is_vowel
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


# Cyrillic letters no Russian word has: Ukrainian і, ї, є, ґ and Belarusian ў.
NOT_RUSSIAN = frozenset("іїєґўІЇЄҐЎ")


def script_of(token: str) -> str:
    if NOT_RUSSIAN & set(token):
        return "xx"  # ніч, їжак: Ukrainian, which no analyzer reads
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


def latin_armenian_entries(lexicon: dict[str, str]):
    """[lexicon] entries, a Latin-typed Armenian word's under its Armenian spelling,
    where its line looks it up: srtis = "sər-tis" or "սըր-տիս" is սրտիս = "սըր-տիս".
    Its value says it is Armenian, in Armenian letters or with a ə or @ for ը; an
    English word's value is ARPABET."""
    for word, value in lexicon.items():
        armenian = any(hy.is_armenian(ch) for ch in value)
        latin = script_of(word) == en.CODE and (armenian or any(ch in "ə@" for ch in value))
        if not latin:
            yield word, value
            continue
        if not armenian:  # sər-tis: each syllable in Armenian letters
            value = "-".join(hy.from_latin(part) for part in value.split("-"))
        yield hy.from_latin(word), value


def override_error(word: str, value: str) -> str | None:
    """Why a [lexicon] entry cannot be used, by the script of its word; None if
    it can, or if no analyzer reads that script."""
    module = ANALYZERS.get(script_of(word))
    return module.override_error(word, value) if module else None


def detect(tokens: list[str]) -> str:
    counts: dict[str, int] = {}
    for t in tokens:
        s = script_of(t)
        if LATIN_WITH_ENDING.fullmatch(t):  # TikTok-ում
            s = hy.CODE
        elif LATIN_WITH_RU_ENDING.fullmatch(t):  # TikTok'е
            s = ru.CODE
        if s and s != "xx":
            counts[s] = counts.get(s, 0) + 1
    if not counts:
        return "xx" if any(script_of(t) == "xx" for t in tokens) else ""
    # a tie goes to the script that is not Latin: XXI դար, iPhone-ом are Armenian, Russian
    return max(counts, key=lambda k: (counts[k], k != en.CODE))


# Vowel letters of scripts ashugh does not analyze, by their base letter: Latin
# (with any accent), Greek, Georgian.
FOREIGN_VOWELS = frozenset("aeiouyæøœαεηιοωυაეიოუаеиоуяюєіїэы")


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


PHRASE_END = re.compile(r"\s*[,.;:!?…—–։՝․]")  # ․ the Armenian middle dot
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


def _glued_to_ampersand(tokens: list[str], text: str | None) -> set[int]:
    """Tokens in Latin capitals written against an & with no space: AT&T, R&B."""
    if not text or "&" not in text:
        return set()
    spans = lyrics.token_spans(text)
    if [t for _, _, t in spans] != tokens:
        return set()
    out = set()
    for k, (a, b, t) in enumerate(spans):
        if t == "&":
            for j in (k - 1, k + 1):
                if 0 <= j < len(spans) and spans[j][2] != "&":
                    x, y, word = spans[j]
                    if (y == a or x == b) and word.isascii() and word.isupper() and len(word) <= 5:
                        out.add(j)
    return out


DOTTED_RE = re.compile(r"(?<![^\W\d_])(?:[A-Za-z]\.){2,}")  # U.S.A., L.A., a.k.a.


def _dotted_letters(tokens: list[str], text: str | None) -> set[int]:
    """Letters of a dotted abbreviation, each said by its name: U-S-Á, not the a of
    the article."""
    if not text or "." not in text:
        return set()
    spans = lyrics.token_spans(text)
    if [t for _, _, t in spans] != tokens:
        return set()
    dotted = [m.span() for m in DOTTED_RE.finditer(text)]
    return {k for k, (a, b, _) in enumerate(spans) if any(x <= a and b <= y for x, y in dotted)}


def _after_apostrophe(tokens: list[str], text: str | None) -> set[int]:
    """Words written after an apostrophe that opens them: 'ere, 'is, 'eart."""
    if not text or not any(ch in text for ch in "'’"):
        return set()
    spans = lyrics.token_spans(text)
    if [t for _, _, t in spans] != tokens:
        return set()
    return {
        k
        for k, (a, _, _) in enumerate(spans)
        if a > 0 and text[a - 1] in "'’" and (a == 1 or not text[a - 2].isalnum())
    }


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
    armenian = latin_words_in_armenian(tokens, in_latin) if lang == hy.CODE else []
    glued = _glued_to_ampersand(tokens, text) | _dotted_letters(tokens, text)
    opened = _after_apostrophe(tokens, text)
    seen: dict[str, Word] = {}
    for k, token in enumerate(tokens):
        if k in glued:  # AT&T, R&B, U.S.A.: letters, whatever word they spell
            words.append(en.analyze_word(token, lexicon, capitals, letters=True))
            continue
        if LATIN_WITH_ENDING.fullmatch(token):  # TikTok-ում, in any line: its ending is Armenian
            words.append(_latin_with_ending(token, lexicon))
            continue
        if armenian and armenian[k]:
            words.append(_from_latin(token, lexicon))
            continue
        if LATIN_WITH_RU_ENDING.fullmatch(token):
            words.append(_latin_with_russian_ending(token, lexicon))
            continue
        if token == "&":  # rock & roll: the line's own and
            and_ = analyze_word_as(AMPERSAND.get(lang, "and"), lexicon)
            and_.text = token
            words.append(and_)
            continue
        if k in opened and script_of(token) == en.CODE:  # 'ere, 'is: here, his
            word = en.analyze_word("'" + token, lexicon, capitals)
            word.text = token
            words.append(word)
            continue
        if token in seen:  # a word the line repeats (la la la): analyzed once, copied
            words.append(replace(seen[token], notes=list(seen[token].notes)))
            continue
        script = script_of(token)
        if script == en.CODE and "@" in token:  # @john: a handle, and no ը in English
            word = en.analyze_word(token.strip("@"), lexicon, capitals)
            word.text = token
        elif script == en.CODE:
            word = en.analyze_word(token, lexicon, capitals)
        elif script == ru.CODE:
            word = ru.analyze_word(token, lexicon, capitals)
        elif script == hy.CODE:
            word = hy.analyze_word(token, lexicon, capitals)
        elif script in ANALYZERS:
            word = ANALYZERS[script].analyze_word(token, lexicon)
        else:
            word = foreign_word(token)
        seen[token] = replace(word, notes=list(word.notes))
        words.append(word)
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
        ru.we_sing(words)
        ru.yo_after_prepositions(words)
        ru.preposition_shift(words)
    if any(w.lang == "en" for w in words):
        en.heteronyms(words)
    end = words[-1] if words else None
    if end is not None and end.lang == "en" and end.clitic and end.norm not in ("a", "an", "the"):
        end.clitic = False  # a stranded preposition is stressed: gone by, roll in
    if end is not None and end.lang == ru.CODE and (end.clitic or end.enclitic):
        ru.stranded(words)  # Скажи мне: да; всё не то; ни с тобой, ни без
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
            and (
                before.size > 1  # with-óut you, a-bóut you, even with nothing before
                or content is not None
                and content.lang == "en"
                and not (content.clitic or content.norm in en.WEAK)
            )
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


# An apostrophe where English verse leaves a letter out (wi', an', tim'rous), not the
# one Latin-typed Armenian writes after an aspirate (t'agavor, ch'em, p'ok'r).
ELISION = re.compile(r"[aeioun]['’]$|[^tpkhs'’]['’](?=[a-z])")
# English words an Armenian line in Latin letters borrows (sirum em qez, baby, Du
# sexy es), long enough that no Armenian word is spelt like them: not a (ա), am,
# in, or boy (բոյ).
BORROWED_ENGLISH = (
    {w for w in COMMON_ENGLISH if len(w) >= 4}
    | {"oh", "yeah", "hey"}
    | set(
        """sexy party next crazy money girl girls forever together music feeling body lady
        honey sugar sweet shine high higher world light lights alright okay cool style flow
        beat vibe mood crush sorry please thanks kiss call phone club drink champagne darling
        beautiful pretty smile happy goodbye hello welcome fashion queen king boss cash game
        play player team wanna gonna gotta everybody somebody nobody alone lonely dancing
        party crazy fire rain stars star sunshine summer weekend tonight""".split()
    )
)
# Spellings no English word has: q without u (kyanq, qez), @ and ə for ը.
STRONG_ARMENIAN = re.compile(r"q(?!u)|[@ə]")


def _armenian_word(low: str, shortest: int = 3) -> bool:
    """A Latin-typed word that spells a listed Armenian one: ari արի, bari բարի, jan
    ջան, mej մեջ; two letters with shortest=2 (du, im, es)."""
    return len(low) >= shortest and hy.from_latin(low) in hy.short_words()


def _looks_armenian(token: str) -> bool:
    """A Latin word of an Armenian song's English-looking line that is Armenian: one
    spelt as no English word is (kyanqs, qez), or one English lacks (srtis, gna);
    higher, laughing and highway are English, gh and all."""
    low = token.lower()
    return bool(STRONG_ARMENIAN.search(low)) or not en.known(low)


def latin_words_in_armenian(tokens: list[str], in_latin: bool) -> list[bool]:
    """Which Latin-letter words of an Armenian song's line are Armenian: in a line
    of Armenian typed in Latin every one but an English word it borrows (baby,
    party); in an English line those spelt as Armenian (kyanqs, sirum), an
    auxiliary after one (sirum em), and a short Armenian word beside one (Du im
    srtis mej es, my love)."""
    out: list[bool] = []
    for token in tokens:
        low = token.lower().strip("'")
        if script_of(token) != en.CODE:
            out.append(False)
        elif in_latin:
            out.append(low not in BORROWED_ENGLISH)
        else:
            after = bool(out) and out[-1] and low in hy.LATIN_AUXILIARIES
            out.append(after or _looks_armenian(low))
    if not in_latin:  # du, im, es beside an Armenian word, read both ways along the line
        for order in (range(len(tokens)), range(len(tokens) - 1, -1, -1)):
            for k in order:
                low = tokens[k].lower().strip("'")
                near = [j for j in (k - 1, k + 1) if 0 <= j < len(tokens) and out[j]]
                if (
                    not out[k]
                    and near
                    and script_of(tokens[k]) == en.CODE
                    and len(low) <= 3
                    and low not in COMMON_ENGLISH
                    and _armenian_word(low, shortest=2)
                ):
                    out[k] = True
    return out


def latin_armenian(tokens: list[str]) -> bool:
    """A line of an Armenian song written in Latin letters (Mtnem aygin, qaghem
    vard) rather than an English line within it (I love you, baby): no Armenian
    letter, and, each word once, more Armenian ones (spelt as Armenian, listed as
    Armenian, or not English) than English ones (a common word, an elision like
    wi', or half for another the dictionary has: Burns's thou, start, hasty)."""
    if any(script_of(t) == hy.CODE for t in tokens):
        return False
    latin = list(dict.fromkeys(t.lower() for t in tokens if script_of(t) == en.CODE))
    armenian = english = 0.0
    for t in latin:
        if t in COMMON_ENGLISH or ELISION.search(t):  # wi', an', cow'rin: not t' or k'
            english += 1
        elif STRONG_ARMENIAN.search(t) or _armenian_word(t) or not en.known(t):
            armenian += 1  # qez, ari, bari, jan, gna: Armenian names fill the dictionary
        elif len(t) > 2:
            english += 0.5
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
    # DM-ում, BTS-ի: an abbreviation is its letters, as English spells them
    english = en.known(name.lower()) or en.abbreviation(name) is not None
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


# A name in Latin letters with a Russian case ending: TikTok'е, iPhone-а, Instagram'ами.
LATIN_WITH_RU_ENDING = re.compile(r"([A-Za-z][A-Za-z.]*)['’-]([а-яё]+)")


def _latin_with_russian_ending(token: str, lexicon: dict[str, str]) -> Word:
    """A Latin name with a Russian ending, a Russian word: the name as English says
    it, the ending's vowels sung after it (тик-то́-ке, ин-ста-гра́-ме); the stress
    on the name's last full vowel, as Russian takes English names (айфо́н,
    инстагра́м, but гу́гл, не́тфликс). An English syllabic l is no syllable before
    the ending's vowel: в гу́гле."""
    found = LATIN_WITH_RU_ENDING.fullmatch(token)
    if found is None:
        raise ValueError(f"{token!r} is no Latin name with a Russian ending")
    name, ending = found.groups()
    head = en.analyze_word(name, lexicon)
    first = head.readings[0]
    syllables = list(head.syllables)
    phones = list(first.phones)
    for k, at in enumerate(nuclei(tuple(phones))[: len(syllables)]):  # TikTok is тикток, not тиктак
        letters = syllables[k].text.lower()
        if phones[at] in ("ɑ", "ɔ") and "o" in letters:
            phones[at] = "o"
        elif phones[at] in ("æ", "ɑ") and "a" in letters:
            phones[at] = "a"  # Instagram is инстаграм
    phones = list(adapt_english(phones, ru.CODE))
    voweled = ru.vowel_count(ending) > 0
    if voweled and phones[-2:] == ["ə", "l"] and len(syllables) > 1:  # Google: гугл-е
        del phones[-2]
        last = syllables.pop()
        syllables[-1] = replace(syllables[-1], text=syllables[-1].text + last.text)
    sep = token[len(name)]
    tail = [] if not voweled else ru.split_syllables(ending)
    if tail:
        tail[0] = (sep if sep != "-" else "") + tail[0]
        syllables.extend(Syllable(t) for t in tail)
    else:
        syllables[-1] = replace(syllables[-1], text=syllables[-1].text + token[len(name) :])
    phones.extend(ru.transcribe("т" + ending, -1)[1:])  # unstressed, never word-initial [j]
    stress = max(
        k for k in (first.stress, *first.secondary) if k is not None and k < len(syllables)
    )
    reading = Reading(stress, tuple(phones), token.lower(), "rule")
    return Word(token, token.lower(), ru.CODE, tuple(syllables), (reading,))


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
    # The auxiliary ես is [ɛs], not the pronoun [jɛs], when a linking -ն precedes it;
    # and a word in ե is said [jɛ] but written with a vowel, which the article -ն is
    # written before to link onto: աղջիկն եկավ
    return is_vowel(first(w)) or w.norm in hy.AUXILIARIES or w.norm.startswith(("ե", "և"))
