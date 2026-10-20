"""Russian: syllables, stress lookup with ё restoration, and a phonetic transcription.

Syllables are vowels, so counting is easy; stress is not. Where a word's stress
comes from, in order:

1. a mark in the text: an acute (замо́к), ё, or one capital vowel (замОк);
2. the spec's [lexicon] table;
3. the bundled OpenRussian table, with ё restored (еще -> ещё; все -> все/всё);
4. poetic and derived forms looked up by their dictionary twin (мгновенье ->
   мгновение, мглою -> мглой, сильней -> сильнее, -ся, не-);
5. otherwise every vowel is a candidate and the meter picks one.

The transcription exists for rhyme: it reduces unstressed vowels, devoices and
assimilates obstruents, and drops the silent consonants of сердце, солнце,
честный, so rhymes are judged by sound rather than spelling.
"""

from __future__ import annotations

from ..model import Reading, Syllable, Word
from ..table import SuffixPrior
from .ru_lexicon import TABLE

SUFFIXES = SuffixPrior("data/ru_suffix.tsv")

CODE = "ru"
NAME = "Russian"

VOWELS = set("аеёиоуыэюя")
ACUTE = "\u0301"

CLITICS = {
    "в",
    "во",
    "на",
    "за",
    "по",
    "под",
    "подо",
    "над",
    "надо",
    "о",
    "об",
    "обо",
    "от",
    "ото",
    "до",
    "из",
    "изо",
    "к",
    "ко",
    "с",
    "со",
    "у",
    "без",
    "безо",
    "для",
    "про",
    "при",
    "и",
    "а",
    "но",
    "да",
    "иль",
    "ли",
    "ль",
    "же",
    "ж",
    "бы",
    "б",
    "не",
    "ни",
    "чтоб",
    "из-за",
    "из-под",
}
ENCLITICS = {"ли", "ль", "же", "ж", "бы", "б", "то", "ка"}
# Polysyllabic function words that verse often leaves unstressed.
WEAK = {
    "через",
    "перед",
    "передо",
    "между",
    "около",
    "после",
    "кроме",
    "или",
    "либо",
    "чтобы",
    "если",
    "будто",
    "словно",
    "даже",
    "тоже",
    "также",
    "ибо",
    "разве",
    "нибудь",
}
# Pronouns are weakly stressed in verse and may sit on a weak beat: вспоминай эту ночь.
WEAK |= set(
    """
    меня тебя себя мне его ему её ее ею нею него нему неё нее ими ними нами вами мною
    тобой собой тобою собою кого кому чего чему
    этот эта это эти эту этой этом этим этих этого этому этою
    мой моя моё мое мою мои моей моих моим моего моему моими
    твой твоя твоё твое твою твои твоей твоих твоим твоего твоему твоими
    свой своя своё свое свою свои своей своих своим своего своему своими
    наша наше наши нашу нашей наших нашим нашего нашему ваша ваше ваши вашу вашей
    ваших вашим вашего вашему
    """.split()
)
# Pronoun forms and function words the table lacks: spelling, stressed vowels.
CORE: dict[str, tuple[str, tuple[int, ...]]] = {
    "кого": ("кого", (1,)),
    "чему": ("чему", (1,)),
    "него": ("него", (1,)),
    "нему": ("нему", (1,)),
    "нее": ("неё", (1,)),
    "неё": ("неё", (1,)),
    "нею": ("нею", (0,)),
    "ею": ("ею", (0,)),
    "ими": ("ими", (0,)),
    "ними": ("ними", (0,)),
    "нами": ("нами", (0,)),
    "вами": ("вами", (0,)),
    "мною": ("мною", (0,)),
    "тобой": ("тобой", (1,)),
    "собой": ("собой", (1,)),
    "тобою": ("тобою", (1,)),
    "собою": ("собою", (1,)),
    "наши": ("наши", (0,)),
    "ваши": ("ваши", (0,)),
    "нашего": ("нашего", (0,)),
    "вашего": ("вашего", (0,)),
    "нашей": ("нашей", (0,)),
    "вашей": ("вашей", (0,)),
    "наших": ("наших", (0,)),
    "ваших": ("ваших", (0,)),
    "нашим": ("нашим", (0,)),
    "вашим": ("вашим", (0,)),
    "одна": ("одна", (1,)),
    "одно": ("одно", (1,)),
    "одни": ("одни", (1,)),
    "одного": ("одного", (2,)),
    "одной": ("одной", (1,)),
    "одному": ("одному", (2,)),
    "одним": ("одним", (1,)),
    "одними": ("одними", (1,)),
    "одних": ("одних", (1,)),
    "одну": ("одну", (1,)),
    "тремя": ("тремя", (1,)),
    "четырех": ("четырёх", (2,)),
    "четырёх": ("четырёх", (2,)),
    "наша": ("наша", (0,)),
    "наше": ("наше", (0,)),
    "ваша": ("ваша", (0,)),
    "ваше": ("ваше", (0,)),
    "зачем": ("зачем", (1,)),
    "годы": ("годы", (0,)),
    "буду": ("буду", (0,)),
    "будешь": ("будешь", (0,)),
    "будет": ("будет", (0,)),
    "будем": ("будем", (0,)),
    "будете": ("будете", (0,)),
    "будут": ("будут", (0,)),
    "нашу": ("нашу", (0,)),
    "вашу": ("вашу", (0,)),
    "нашем": ("нашем", (0,)),
    "вашем": ("вашем", (0,)),
    "одном": ("одном", (1,)),
    "годов": ("годов", (1,)),
    "издалека": ("издалека", (3,)),  # the table has only the colloquial издалёка
    "краю": ("краю", (0, 1)),  # кра́ю, and the locative в краю́ the table lacks
    "года": ("года", (0, 1)),  # го́да, and the plural года́ of songs and verse
    "кружит": ("кружит", (0, 1)),  # кружи́т; the table has only кру́жит
    "кружат": ("кружат", (0, 1)),
    "кем-то": ("кем-то", (0,)),
    "из-за": ("из-за", (1,)),
    "из-под": ("из-под", (1,)),
}
PARTICLES = {"то", "либо", "нибудь", "ка", "таки"}
# Nouns whose locative after в, во or на is stressed on the ending: в саду́, на ветру́,
# в крови́. After these prepositions the stem-stressed dative or genitive cannot be meant.
# Some take it after one preposition only: в полку́ but на по́лку, на виду́ but в ви́ду.
SECOND_LOCATIVE = frozenset(
    """
    аду балу бегу берегу бою бору боку борту бреду быту веку верху ветру возу
    газу глазу гробу году дому дубу дыму жару клею кону краю кругу крюку ладу лбу лесу
    льду лугу мелу меду меху миру мозгу мосту мху мысу носу песку пиру плену плоту
    полу порту посту поту пруду пуху раю роду рву рту ряду саду свету слою снегу
    сну соку строю тылу углу усу ходу холоду хмелю цвету чаду часу шагу шелку шкафу
    глуби глуши горсти груди грязи крови мели ночи оси печи пыли руси степи
    тени тиши чести шерсти
    """.split()
)
LOCATIVE_PREPOSITIONS = frozenset({"в", "во", "на"})
LOCATIVE_ONLY_AFTER = {"полку": {"в", "во"}, "связи": {"в", "во"}, "виду": {"на"}, "суку": {"на"}}
# -ого / -его is said -ово / -ево, except in these words.
NOT_OGO = {
    "много",
    "немного",
    "строго",
    "нестрого",
    "убого",
    "дорого",
    "недорого",
    "полого",
    "отлого",
}
REWRITES = (
    ("ться", "ца"),
    ("тся", "ца"),
    ("стн", "сн"),
    ("здн", "зн"),
    ("рдц", "рц"),
    ("лнц", "нц"),
    ("вств", "ств"),
    ("стл", "сл"),
    ("нтск", "нск"),
    ("ндск", "нск"),
    ("сч", "щ"),
    ("зч", "щ"),
    ("жч", "щ"),
)
WORD_REWRITES = {
    "что": "што",
    "чтобы": "штобы",
    "чтоб": "штоб",
    "ничто": "ништо",
    "конечно": "конешно",
    "скучно": "скушно",
    "нарочно": "нарошно",
    "сегодня": "севодня",
}

CONSONANTS = {
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "ж": "ʒ",
    "з": "z",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "ф": "f",
    "х": "x",
    "ц": "ts",
    "ч": "tʃʲ",
    "ш": "ʃ",
    "щ": "ɕː",
    "й": "j",
}
HARD = set("жшц")
SOFT = set("чщй")
SOFTENING = set("еёиюяь")
IOTATED = {"е": "e", "ё": "o", "ю": "u", "я": "a"}
PLAIN = {"а": "a", "о": "o", "у": "u", "ы": "ɨ", "э": "e", "и": "i"}
DEVOICE = {"b": "p", "v": "f", "g": "k", "d": "t", "z": "s", "ʒ": "ʃ"}
VOICE = {v: k for k, v in DEVOICE.items()}


def is_cyrillic(ch: str) -> bool:
    return "Ѐ" <= ch <= "ӿ"


def vowel_count(word: str) -> int:
    return sum(ch in VOWELS for ch in word)


def read_marks(token: str) -> tuple[str, int | None]:
    """Normalized spelling and the stressed vowel index a mark in token gives, if any."""
    stress = None
    letters: list[str] = []
    vowel_no = -1
    caps = [i for i, ch in enumerate(token) if i > 0 and ch.isupper() and ch.lower() in VOWELS]
    rest_lower = all(not ch.isupper() for i, ch in enumerate(token) if i > 0 and i not in caps)
    cap_mark = caps[0] if len(caps) == 1 and rest_lower else None
    for i, ch in enumerate(token):
        if ch == ACUTE:
            if vowel_no >= 0:
                stress = vowel_no
            continue
        low = ch.lower()
        if low in VOWELS:
            vowel_no += 1
            if i == cap_mark or low == "ё":
                stress = vowel_no
        letters.append(low)
    return "".join(letters), stress


def split_syllables(word: str) -> list[str]:
    """Orthographic syllables for display: мо-ро-зы, толь-ко, се-мья, вой-на."""
    if "-" in word:
        parts: list[str] = []
        for part in word.split("-"):
            if parts and not vowel_count(parts[-1].lower()):
                parts[-1] += part  # a vowelless piece joins the next one
            else:
                parts.append(part)
        return [s for part in parts for s in split_syllables(part)]
    low = word.lower()
    idx = [i for i, ch in enumerate(low) if ch in VOWELS]
    if not idx:
        return [word] if word else []
    cuts = []
    for a, b in zip(idx, idx[1:]):
        gap = low[a + 1 : b]
        if len(gap) <= 1:
            k = len(gap) if gap in ("й", "ь", "ъ") else 0
        elif gap[0] == "й":
            k = 1
        elif len(gap) >= 3:
            two = gap[-1] in "рл" and gap[-2] not in "рлмнйьъ"
            k = len(gap) - (2 if two else 1)  # чест-ных, цен-тра
        elif gap[0] in "рлмн" and gap[1] not in "ьъ":
            k = 1  # кар-та
        elif gap[0] in "сзшж" or gap[1] in "рлвмнй" or gap[1] in "ьъ":
            k = 0  # се-стра, ви-хри, до-бро
        else:
            k = 1  # чест-ных, шут-ку, луч-ше
        cuts.append(a + 1 + k)
    pieces = []
    start = 0
    for cut in cuts:
        pieces.append(word[start:cut])
        start = cut
    pieces.append(word[start:])
    return pieces


def _rewrite(spelling: str) -> str:
    s = WORD_REWRITES.get(spelling, spelling)
    if s.endswith(("ого", "его")) and s not in NOT_OGO and s != "ого":
        s = s[:-2] + "в" + s[-1]
    for old, new in REWRITES:
        s = s.replace(old, new)
    return s


def _reduce(vowel: str, soft: bool, last: bool) -> str:
    if vowel in ("a", "o"):
        return "ɪ" if soft and not last else "ə"
    if vowel == "e":
        return "ɪ" if soft else "ɨ"
    if vowel == "i":
        return "ɪ"
    return vowel


def transcribe(spelling: str, stress: int | None) -> tuple[str, ...]:
    s = _rewrite(spelling.replace("-", ""))
    total = vowel_count(s)
    out: list[str] = []
    vowel_no = 0
    prev = ""
    for i, ch in enumerate(s):
        nxt = s[i + 1] if i + 1 < len(s) else ""
        if ch in CONSONANTS:
            ph = CONSONANTS[ch]
            if ch not in HARD and ch not in SOFT and nxt in SOFTENING:
                ph += "ʲ"
            out.append(ph)
        elif ch in VOWELS:
            after_consonant = prev in CONSONANTS and prev != "й"
            if ch in IOTATED and not after_consonant:
                out.append("j")
            elif ch == "и" and prev == "ь":
                out.append("j")
            vowel = IOTATED.get(ch) or PLAIN[ch]
            if ch == "и" and prev in HARD:
                vowel = "ɨ"
            soft = (ch in IOTATED or ch == "и") or prev in SOFT
            if prev in HARD:
                soft = False
            if vowel_no != stress:
                vowel = _reduce(vowel, soft, vowel_no == total - 1)
            out.append(vowel)
            vowel_no += 1
        prev = ch
    # Final devoicing and regressive voicing assimilation, right to left.
    for i in range(len(out) - 1, -1, -1):
        ph = out[i]
        base = ph.rstrip("ʲ")
        tail = ph[len(base) :]
        nxt = out[i + 1] if i + 1 < len(out) else None
        nxt_base = nxt.rstrip("ʲ") if nxt else None
        if base in DEVOICE:
            if nxt is None or nxt_base in VOICE or nxt_base in ("x", "ts", "tʃ", "ɕː"):
                out[i] = DEVOICE[base] + tail
        elif base in VOICE and nxt_base in DEVOICE and nxt_base != "v":
            out[i] = VOICE[base] + tail
    return tuple(out)


def _shift_lookup(norm: str) -> list[tuple[str, tuple[int, ...]]]:
    """Look up a form the table lacks through its dictionary twin."""
    found: list[tuple[str, tuple[int, ...]]] = []

    def twin(form: str, remap) -> None:
        for spelling, stress in TABLE.variants(form) or _mono(form):
            mapped = tuple(sorted({remap(p) for p in stress}))
            found.append((norm if "ё" not in spelling else _carry_yo(norm, spelling), mapped))

    # мгновенье -> мгновение: the ие vowel pair collapses into ье
    for pair in ("ье", "ья", "ью", "ьи"):
        at = norm.rfind(pair)
        if at > 0:
            q = vowel_count(norm[:at])
            twin(norm[:at] + "и" + norm[at + 1 :], lambda p, q=q: p if p <= q else p - 1)
            break
    for short, full in (("ою", "ой"), ("ею", "ей")):
        if norm.endswith(short):
            twin(norm[:-2] + full, lambda p: p)
    if norm.endswith("ей") and not found:
        twin(norm[:-2] + "ее", lambda p: p)
    for suffix in ("ся", "сь"):
        if norm.endswith(suffix) and not found:
            twin(norm[:-2], lambda p: p)
    for prefix in ("не", "ни"):
        if norm.startswith(prefix) and not found and vowel_count(norm) > 2:
            twin(norm[2:], lambda p: p + 1)
    if not found:
        size = vowel_count(norm)
        for form in verb_twins(norm):
            stress = TABLE.get(form)
            if stress and all(p < size for p in stress):
                found.append((norm, stress))
                break
    return found


ALTERNATIONS = (("д", "ж"), ("т", "ч"), ("с", "ш"), ("з", "ж"), ("ст", "щ"), ("ск", "щ"))
LABIALS = set("бпвмф")
PARTICIPLE_ENDINGS = (
    "ий", "ая", "ее", "ие", "его", "ей", "ему", "им", "их", "ими", "ую", "ем", "ою", "ее",
)  # fmt: skip


def verb_twins(norm: str) -> list[str]:
    """Dictionary forms that share a gerund's or participle's stress, most telling first.

    теряя -> теряю (1st person), видя -> вижу, томясь -> томлюсь; начав -> начать
    (infinitive), упав -> упасть; создавший -> создать; враждующих -> враждуют.
    """
    out: list[str] = []
    reflexive = norm.endswith(("сь", "ся")) and len(norm) > 4
    base = norm[:-2] if reflexive else norm
    sg_tail, pl_tail, inf_tail = ("сь", "ся", "ся") if reflexive else ("", "", "")
    if base.endswith(("я", "а")) and len(base) > 2:
        stem = base[:-1]
        if base.endswith("я"):
            out.append(stem + "ю" + sg_tail)
            if stem[-1:] in LABIALS:
                out.append(stem + "лю" + sg_tail)
            for old, new in ALTERNATIONS:
                if stem.endswith(old):
                    out.append(stem[: -len(old)] + new + "у" + sg_tail)
            out += [stem + "ят" + pl_tail, stem + "ют" + pl_tail]
        else:
            out += [stem + "у" + sg_tail, stem + "ат" + pl_tail]
    for tail, inf in (("вшись", "ться"), ("вши", "ть"), ("в", "ть")):
        if norm.endswith(tail) and len(norm) > len(tail) + 1:
            stem = norm[: -len(tail)]
            out += [stem + inf, stem + "с" + inf]
    for ending in PARTICIPLE_ENDINGS:
        word = base if reflexive else norm
        if not word.endswith("вш" + ending):
            continue
        stem = word[: -len("вш" + ending)]
        out.append(stem + "ть" + inf_tail)
        break
    for marker, plural in (("ющ", "ют"), ("ущ", "ут"), ("ящ", "ят"), ("ащ", "ат")):
        word = base if reflexive else norm
        for ending in PARTICIPLE_ENDINGS:
            if word.endswith(marker + ending):
                stem = word[: -len(marker + ending)]
                # the participle's own nominative first: спящим -> спящий (спят has no
                # stress to copy); then the verb's 3rd person plural
                out += [stem + marker + "ий" + pl_tail, stem + plural + pl_tail]
    return out


def suffix_prior(norm: str) -> int | None:
    """Vowels most likely to follow the stress of an unknown word, from its ending."""
    return SUFFIXES.after(norm)


def _mono(form: str) -> list[tuple[str, tuple[int, ...]]]:
    return [(form, (0,))] if vowel_count(form) == 1 else []


def _carry_yo(norm: str, twin: str) -> str:
    """Restore in norm the ё that its twin spelling has, where the letters line up."""
    chars = list(norm)
    for i, (a, b) in enumerate(zip(norm, twin)):
        if a == "е" and b == "ё":
            chars[i] = "ё"
    return "".join(chars)


def _lexicon_readings(norm: str) -> list[Reading]:
    options: list[tuple[str, tuple[int, ...], str]] = []
    if norm in CORE:
        options.append((*CORE[norm], "lexicon"))
    else:
        for spelling, stress in TABLE.variants(norm):
            options.append((spelling, stress, "lexicon"))
    if not options and "-" in norm:
        head, _, tail = norm.rpartition("-")
        parts = [(head, 0)] if tail in PARTICLES else [(head, 0), (tail, vowel_count(head))]
        for part, offset in parts:
            if vowel_count(part) == 1:
                stresses = [0]
            else:
                stresses = [r.stress for r in _lexicon_readings(part) if r.stress is not None]
            options.extend((norm, (p + offset,), "lexicon") for p in stresses)
    if not options:
        for spelling, stress in _shift_lookup(norm):
            options.append((spelling, stress, "lexicon"))
    readings = []
    for spelling, stress, source in options:
        for p in stress:
            readings.append(Reading(p, transcribe(spelling, p), spelling, source))
    return readings


def _user_readings(value: str) -> list[Reading]:
    norm, stress = read_marks(value.replace("-", ""))
    if stress is None:
        stress = 0 if vowel_count(norm) == 1 else None
    if stress is None:
        return []
    return [Reading(stress, transcribe(norm, stress), norm, "user")]


def analyze_word(token: str, overrides: dict[str, str] | None = None) -> Word:
    norm, marked = read_marks(token)
    shown = token.replace(ACUTE, "")
    syllables = tuple(Syllable(s) for s in split_syllables(shown)) if vowel_count(norm) else ()
    n = len(syllables)
    clitic = norm in CLITICS
    word = Word(
        text=token,
        norm=norm,
        lang=CODE,
        syllables=syllables,
        readings=(),
        weak=clitic or n == 1 or norm in WEAK,
        clitic=clitic,
        enclitic=norm in ENCLITICS,
    )
    user = (overrides or {}).get(norm) or (overrides or {}).get(norm.replace("ё", "е"))
    readings: list[Reading] = []
    if marked is not None:
        readings = [Reading(marked, transcribe(norm, marked), norm, "mark")]
        word.clitic = False
    elif user:
        readings = _user_readings(user)
    if not readings and n == 0:
        readings = [Reading(None, transcribe(norm, None), norm, "clitic")]
    elif not readings and n == 1:
        spellings = [norm] + [s for s, _ in TABLE.variants(norm) if s != norm]
        source = "clitic" if clitic else "rule"
        readings = [Reading(0, transcribe(s, 0), s, source) for s in spellings]
    elif not readings:
        readings = _lexicon_readings(norm)
    if not readings:
        readings = [
            Reading(p, transcribe(norm, p), norm, "guess", penalty=cost)
            for p, cost in SUFFIXES.order(norm.replace("-", ""), n)
        ]
        word.notes.append("stress unknown")
    word.readings = tuple(readings)
    return word


def second_locatives(words: list[Word]) -> None:
    """End-stress the second locative after в, во, на: на берегу́, в крови́."""
    for prev, w in zip(words, words[1:]):
        if w.lang != CODE or prev.norm not in LOCATIVE_PREPOSITIONS:
            continue
        allowed = LOCATIVE_ONLY_AFTER.get(w.norm)
        if allowed is not None:
            if prev.norm not in allowed:
                continue
        elif w.norm not in SECOND_LOCATIVE or w.size < 2:
            continue
        if w.readings and w.readings[0].source in ("mark", "user"):
            continue
        last = w.size - 1
        w.readings = (Reading(last, transcribe(w.norm, last), w.norm, "lexicon"),)
