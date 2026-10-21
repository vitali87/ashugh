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

import re
import unicodedata
from dataclasses import replace
from functools import cache
from importlib import resources

from .. import lyrics
from ..model import Reading, Syllable, Word
from ..table import SuffixPrior
from . import ru_names, ru_slang
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
ENCLITICS = {"ли", "ль", "же", "ж", "бы", "б", "то", "ка", "тя"}  # тя: люблю́ тя
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
    "только",
}
# Pronouns are weakly stressed in verse and may sit on a weak beat: вспоминай эту ночь.
WEAK |= set(
    """
    она оно они
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
    # The plural ветра́ of songs and verse, which the table lacks.
    "ветра": ("ветра", (0, 1)),
    # духи́ (perfume) beside ду́хи (spirits): твоих духо́в
    **{f: (f, (0, 1)) for f in "духов духам духами духах".split()},
    # plural-only nouns whose stress moves to the ending, and the numerals the table lacks
    **{f: (f, (1, 0)) for f in "кудрей кудрям кудрями кудрях".split()},
    **{f: (f, (1,)) for f in "обоих обоим обоими обеих обеим обеими полутора".split()},
    "полторы": ("полторы", (2,)),
    **{f: (f, (1,)) for f in "ветров ветрам ветрами ветрах".split()},
    # начался́, началось́: the table also lists the colloquial на́чался.
    "начался": ("начался", (2,)),
    "началось": ("началось", (2,)),
    "начались": ("начались", (2,)),
    "диджей": ("диджей", (1,)),
    # First names the table lacks, by their stressed vowel.
    **{
        name: (name, (k,))
        for k, names in (
            (
                0,
                "саша маша даша катя оля лена аня миша дима ваня петя коля игорь павел "
                "анна ольга дмитрий борис вера надя таня",
            ),
            (
                1,
                "наташа татьяна ирина андрей сергей светлана полина владимир мария елена "
                "иван олег марина алина кристина галина людмила",
            ),
            (2, "иисус александр михаил николай анастасия"),
            (3, "екатерина"),
        )
        for name in names.split()
    },
    "алёна": ("алёна", (1,)),
    # The table stresses бант on its ending (банты́); it is ба́нт throughout.
    **{f: (f, (0,)) for f in "банта банту бантом банте банты бантов бантам бантами бантах".split()},
    # спеть is missing from the dump; its спою came from elsewhere as спо́ю.
    **{
        f: (f.replace("е", "ё") if "ё" not in f and f != "спою" and f != "споют" else f, (1,))
        for f in "спою споешь споёшь споет споёт споем споём споете споёте споют".split()
    },
    # атла́с (satin) beside а́тлас (atlas), which is all the table has.
    **{
        f: (f, (0, 1))
        for f in (
            "атлас атласа атласу атласом атласе атласы атласов атласам атласами атласах"
        ).split()
    },
    # Names with ё, written without it as often as not: Серёжа, not Сере́жа.
    **{
        k: (v, (s,))
        for v, s in (("серёжа", 1), ("фёдор", 0), ("семён", 1), ("алёша", 1), ("артём", 1))
        for k in (v, v.replace("ё", "е"))
    },
    "дождалась": ("дождалась", (2,)),  # the dictionary dump's row is garbled
    **{k: ("ё-моё", (0, 2)) for k in ("е-мое", "ё-моё", "е-моё")},
    # Verse's forms and words the table lacks or lists without a stress mark.
    "ветры": ("ветры", (0,)),
    "крылах": ("крылах", (1,)),
    "светает": ("светает", (1,)),
    "вослед": ("вослед", (1,)),
    "впотьмах": ("впотьмах", (1,)),
    # Numerals in their oblique cases, which the dump lists bare: пяти́, четырьмя́.
    **{
        f: (f, (sum(ch in "аеёиоуыэюя" for ch in f) - 1,))
        for f in (
            "пяти шести семи восьми девяти десяти двадцати тридцати пятью шестью семью "
            "девятью десятью восьмью восемью двадцатью тридцатью двумя тремя четырьмя "
            "двоих троих двоим троим пятерых шестерых семерых четверых пятерым"
        ).split()
    },
    # The plural of год is лета́ in the dump; года́м and годо́в are what is said.
    **{f: (f, (1,)) for f in "годам годами годах годов".split()},
    # не грусти́ before гру́сти of грусть, which a preposition usually announces
    "грусти": ("грусти", (1, 0)),
    "дабы": ("дабы", (0,)),  # the table's даба́ is a misprint
    "посреди": ("посреди", (2,)),
    # дождаться's present, which the dump's garbled row lacks: дожду́сь, дождёшься
    **{
        k: (f, (1,))
        for f in "дождусь дождёшься дождётся дождёмся дождётесь дождутся".split()
        for k in (f, f.replace("ё", "е"))
    },
    # The far more frequent word first, where the table ranks a rarer verb above it:
    # мою́ (my) before мо́ю (I wash), стоя́т (stand) before сто́ят (cost), выходи́ (come
    # out) before вы́ходи (nurse), жила́ (lived) before жи́ла (vein).
    "мою": ("мою", (1, 0)),
    "стоим": ("стоим", (1, 0)),
    "стоят": ("стоят", (1, 0)),
    "выходи": ("выходи", (2, 0)),
    "жила": ("жила", (1, 0)),
    # Slang and loanwords of songs the dictionary lacks.
    **{
        f: (f, (k,))
        for k, forms in (
            (0, "сорян селфи сторис"),
            (
                1,
                "онлайн офлайн ваще ютуб тикток плейлист плейлиста тусить тусил тусила "
                "тусили тусим тусит тусят кринжовый кринжово",
            ),
            (2, "инстаграм инстаграма инстаграме"),
        )
        for f in forms.split()
    },
    # The dump's colloquial све́рлит and ма́стерски for the norm сверли́т, мастерски́; and
    # зна́чимость beside значи́мость, which dictionaries give too.
    **{f: (f, (1,)) for f in "сверлю сверлишь сверлит сверлим сверлите сверлят".split()},
    "мастерски": ("мастерски", (2,)),
    # the norm first, and the stem stress verse uses too: бледна́ / бле́дна, тонки́ / то́нки
    # сани in the dump is са́ней, са́ням; the norm is сане́й, саня́м, as its аэросане́й
    **{f: (f, (1,)) for f in "саней саням санями санях".split()},
    "бледна": ("бледна", (1, 0)),
    "тонки": ("тонки", (1, 0)),
    **{f: (f, (0, 1)) for f in "значимость значимости значимостью".split()},
    "баю": ("баю", (1,)),  # the lullaby's баю́-ба́юшки-баю́, not ба́ю of ба́ять
    "баюшки": ("баюшки", (0,)),
    "кого": ("кого", (1,)),
    "чему": ("чему", (1,)),
    # The table has кому and никого only from ком (a lump) and the archaic никой.
    "кому": ("кому", (1,)),
    "никого": ("никого", (2,)),
    "никому": ("никому", (2,)),
    "никем": ("никем", (1,)),
    **{f: (f, (0,)) for f in "некому нечему некем нечем".split()},
    # пе́нье is verse's пе́ние; the table has only пенье́ of пеньё (stumps).
    **{f: (f, (0,)) for f in "пенье пенья пенью пеньем".split()},
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
    "кружится": ("кружится", (0, 1)),  # кружи́тся; the table has only кру́жится
    "кружатся": ("кружатся", (0, 1)),
    "искрится": ("искрится", (1,)),  # искри́тся; the table says и́скрится
    "искрятся": ("искрятся", (1,)),
    "кем-то": ("кем-то", (0,)),
    "из-за": ("из-за", (1,)),
    "из-под": ("из-под", (1,)),
}
PARTICLES = {"то", "либо", "нибудь", "ка", "таки"}
YO_NAMES = {"петр": "пётр", "трех": "трёх"}  # one-syllable forms the table lacks
# One-syllable words whose е spelling is a word of its own: чем (than, with what),
# not чём; сек (a second), not сёк.
NOT_YO = {"сек", "чем"}
# Nouns whose locative after в, во or на is stressed on the ending: в саду́, на ветру́,
# в крови́. After these prepositions the stem-stressed dative or genitive cannot be meant.
# Some take it after one preposition only: в полку́ but на по́лку, на виду́ but в ви́ду.
SECOND_LOCATIVE = frozenset(
    """
    аду балу бегу берегу бою бору боку борту бреду быту веку верху ветру возу
    аэропорту газу глазу гробу году дому дубу дыму жару клею кону краю кругу крюку ладу лбу лесу
    льду лугу мелу меду меху миру мозгу мосту мху мысу носу песку пиру плену плоту
    полу порту посту поту пруду пуху раю роду рву рту ряду саду свету слою снегу
    сну соку строю тылу углу усу ходу холоду хмелю цвету чаду часу шагу шелку шкафу пылу
    глуби глуши горсти груди грязи крови мели ночи оси печи пыли руси степи
    тени тиши чести шерсти
    """.split()
)
LOCATIVE_PREPOSITIONS = frozenset({"в", "во", "на"})
# After these the noun is in the genitive or dative, stressed on its stem: без кра́ю, к кра́ю.
CASE_PREPOSITIONS = frozenset({"без", "до", "из", "от", "у", "для", "к", "ко", "по"})
# Nouns whose stressed locative (на двери́, в сети́, на цепи́) is spelt like their plural,
# which follows в and на as often (стучать в две́ри, попасть в се́ти): both stay
# possible, the locative first.
LOCATIVE_OR_PLURAL = frozenset({"двери", "сети", "цепи"})
# Pairs where the stress may move from the noun onto the preposition: по́ лесу, на́ ночь,
# за́ руку. Both readings stay possible; the shifted one costs the meter a little.
PREPOSITION_SHIFT = {
    "на": set(
        """берег воду гору день ночь зиму лето год два три дом ногу ноги руку руки
        голову спину бок пол нос плечи поле небо море мель смех слух спор сторону
        душу борт ветер""".split()
    ),
    "за": set(
        """руку руки ногу ноги голову волосы бок борт город год день ночь зиму лето
        душу уши плечи спину нос полночь морем""".split()
    ),
    "по": set("лесу полю морю небу миру снегу лугу полу двое трое сердцу плечу уху".split()),
    "из": set("лесу дому виду носу".split()),
    # не́ был, не́ было, не́ дали; but не была́, не дала́
    "не": set("был было были дал дало дали жил жило жили пил пило пили".split()),
    "под": set("гору ноги руку руки вечер нос".split()),
    "без": set("вести толку году".split()),
    "до": set("дому смерти полу неба".split()),
    "от": set("роду".split()),
}
LEAN_COST = 0.2
# не takes the stress of these by the norm (не́ был, не́ дал); не́ были and не бы́ли
# are both heard, so those stay a choice
NE_FIRST = frozenset("был было дал дало дали жил жило пил пило".split())
# не́ с кем, не́ о чем, не́ за что: не, a preposition and one of these, stressed on не
NE_PRONOUNS = frozenset("кем чем что кому кого чего ком чём чему".split())
LOCATIVE_ONLY_AFTER = {
    "полку": {"в", "во"},
    "связи": {"в", "во"},
    "виду": {"на"},
    "суку": {"на"},
    "лету": {"на"},  # на лету́, but к ле́ту
}
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
    ("гк", "хк"),  # лёгкий, мягко
    ("гч", "хч"),  # мягче
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


def _yo_only_mark(token: str) -> bool:
    """Whether the only stress mark in token is a written ё (no acute, no capital)."""
    return read_marks(token.replace("ё", "е").replace("Ё", "Е"))[1] is None


# An apostrophe after a vowel of a Cyrillic word, the stress mark of OpenRussian
# and of plain keyboards: замо'к, за'мок.
APOSTROPHE_MARK = re.compile("([аеёиоуыэюяАЕЁИОУЫЭЮЯ])'(?=[а-яё]|$)")


def read_marks(token: str) -> tuple[str, int | None]:
    """Normalized spelling and the stressed vowel index a mark in token gives, if any."""
    stress = None
    letters: list[str] = []
    vowel_no = -1
    caps = [i for i, ch in enumerate(token) if i > 0 and ch.isupper() and ch.lower() in VOWELS]
    rest_lower = all(not ch.isupper() for i, ch in enumerate(token) if i > 0 and i not in caps)
    cap_mark = caps[0] if len(caps) == 1 and rest_lower and not token.isupper() else None
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


def override_error(word: str, value: str) -> str | None:
    """Why a [lexicon] entry cannot be used, or None: замок = замо́к, замОк or ё."""
    spelled, stress = read_marks(value.replace("-", ""))
    if spelled.replace("ё", "е") != read_marks(word)[0].replace("-", "").replace("ё", "е"):
        return f"{value!r} spells a different word"
    if stress is None and vowel_count(spelled) > 1:
        return f"{value!r} marks no stress: write it like замо́к, замОк, or with ё"
    return None


ONSETS_IN_V = frozenset("цв зв св кв дв гв шв хв чв жв".split())  # цвет, звук; not тв: чувст-во


def _onset(cs: str) -> bool:
    """Whether two consonants can begin a syllable: ст, св, гр, мн."""
    return len(cs) == 2 and (cs[0] in "сзшж" or cs[1] in "рлвмнй")


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
        elif gap.endswith("дж") and low[: b - 1] not in ("под", "над"):
            k = len(gap) - 2  # ди-джей, бю-джет: дж is one sound; под-жечь is not
        elif gap[0] == gap[1] and (len(gap) == 2 or _onset(gap[1:])):
            k = 1  # кас-са, рас-свет, без-зву-чный; but групп-ка
        elif len(gap) >= 3:
            two = gap[-1] in "рл" and gap[-2] not in "рлмнйьъ"
            two = two or gap[-2:] in ONSETS_IN_V
            k = len(gap) - (2 if two else 1)  # чест-ных, цен-тра, трёх-цве-тный
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


def _reduce(vowel: str, soft: bool, last: bool, post: bool = False) -> str:
    if vowel in ("a", "o"):
        return "ɪ" if soft and not last else "ə"
    if vowel == "e":  # after ж ш ц: жена [ʐɨ], but сердце [tsə] after the stress
        return "ɪ" if soft else ("ə" if post else "ɨ")
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
                post = stress is not None and vowel_no > stress
                vowel = _reduce(vowel, soft, vowel_no == total - 1, post)
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
    # A double consonant at the end or before another consonant is said single:
    # класс [klas], грипп, искусство [iskustvə].
    vowels = set(PLAIN.values()) | set(IOTATED.values()) | {"ə", "ɐ", "ɪ", "ʊ", "ɨ"}
    for i in range(len(out) - 1, 0, -1):
        after = out[i + 1] if i + 1 < len(out) else None
        if out[i] == out[i - 1] and out[i] not in vowels and (after is None or after not in vowels):
            del out[i]
    return tuple(out)


# Prefixes of two letters or more: у-, о-, с- and в- split too many words wrongly
# (у-сладила). A neuter in -ло is too often no verb (западло).
VERB_PREFIXES = sorted(
    "пере пред при про пре разо раз рас без бес взо воз вос вз вс изо из ис недо "
    "надо над подо под обо об ото от по до за на со во".split(),
    key=len,
    reverse=True,
)
VERB_ENDINGS = ("л", "ла", "ли", "лся", "лась", "лось", "лись", "ть", "ться")


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
    # Folk and old verse write -ся in full after a vowel where speech has -сь
    # (улыба́лася, не ложи́ся, бою́ся): its twin is the -сь form, not the bare stem
    # (ло́жи, theatre boxes).
    if norm.endswith("ся") and norm[-3:-2] in VOWELS and not found and norm[:-2] not in CLITICS:
        twin(norm[:-2] + "сь", lambda p: p)
    # стараясь is стара́юсь's gerund, not ста́рая with сь: a gerund asks its verb first.
    gerund = norm.endswith(("ясь", "ась")) and not norm.endswith("лась")
    for suffix in ("ся", "сь"):
        # неся is несу́'s gerund, not не with -ся
        if norm.endswith(suffix) and not found and not gerund and norm[:-2] not in CLITICS:
            twin(norm[:-2], lambda p: p)
    for prefix in ("не", "ни"):
        if norm.startswith(prefix) and not found and vowel_count(norm) > 2:
            twin(norm[2:], lambda p: p + 1)
    if not found:
        found += [(norm, stress) for stress in participle_stresses(norm)]
    if not found:
        size = vowel_count(norm)
        for form in verb_twins(norm):
            stress = TABLE.stresses(form)
            if stress and all(p < size for p in stress):
                found.append((norm, stress))
                break
    if gerund and not found:
        twin(norm[:-2], lambda p: p)
    # A prefixed verb form the table lacks is stressed as its base is (отжила́ as жила́,
    # подзабы́ла as забы́ла), but for вы-, which takes the stress itself.
    if not found and norm.endswith(VERB_ENDINGS):
        for prefix in VERB_PREFIXES:
            rest = norm[len(prefix) :]
            if norm.startswith(prefix) and vowel_count(rest) > 1:
                q = vowel_count(prefix)
                twin(rest, lambda p, q=q: p + q)
                if found:
                    break
    return found


ALTERNATIONS = (("д", "ж"), ("т", "ч"), ("с", "ш"), ("з", "ж"), ("ст", "щ"), ("ск", "щ"))
LABIALS = set("бпвмф")
PARTICIPLE_ENDINGS = (
    "ий", "ая", "ее", "ие", "его", "ей", "ему", "им", "их", "ими", "ую", "ем", "ою", "ее",
)  # fmt: skip


# A present participle of the second conjugation is stressed as its infinitive
# (кормя́щий as корми́ть, though ко́рмят), but for a few stressed as the 3rd plural
# (лю́бящий, ле́чащий, ды́шащий) and слу́жащий, the noun beside служа́щий.
PARTICIPLE_LIKE_PLURAL = {"люб": False, "леч": False, "дыш": False, "служ": True}


def participle_stresses(norm: str) -> list[tuple[int, ...]]:
    """The stresses of a second-conjugation participle in -ящ-/-ащ- the table lacks."""
    reflexive = norm.endswith(("ся", "сь"))
    word, tail = (norm[:-2], "ся") if reflexive else (norm, "")
    for marker, plural, infinitives in (("ящ", "ят", "ить еть ять"), ("ащ", "ат", "ать ить еть")):
        ending = next((e for e in PARTICIPLE_ENDINGS if word.endswith(marker + e)), None)
        if ending is None or len(word) == len(marker + ending):
            continue
        stem = word[: -len(marker + ending)]
        forms = [stem + i + tail for i in infinitives.split()]
        infinitive = next((st for f in forms if (st := TABLE.stresses(f))), None)
        third = TABLE.stresses(stem + plural + tail)
        kept = next((v for root, v in PARTICIPLE_LIKE_PLURAL.items() if stem.endswith(root)), None)
        if kept is None and infinitive:
            return [infinitive]
        out = [s for s in (third, infinitive if kept else None) if s]
        return list(dict.fromkeys(out))
    return []


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
            if stem[-1:] in "дтсзб":
                out.append(stem + "у" + sg_tail)  # идя́ as иду́, неся́ as несу́
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


PLURAL_ENDINGS = ("ами", "ями", "ах", "ях", "ам", "ям")
# Nouns used only in the plural, whose oblique forms the table may lack.
PLURALIA = frozenset(
    """сумерки качели ножницы брюки джинсы шорты трусы очки весы ворота сани сутки
    дрожжи деньги именины каникулы обои перила поминки похороны сливки ясли грабли
    вилы клещи тиски шахматы шашки хлопоты консервы мемуары джунгли дебри потёмки
    задворки заморозки сени штаны""".split()
)


def _plural_oblique(norm: str) -> list[tuple[str, tuple[int, ...]]]:
    """An oblique plural the table lacks, from its nominative plural stressed on
    the stem: a noun used only in the plural keeps that stress (су́мерках,
    каче́лях, но́жницах)."""
    for ending in PLURAL_ENDINGS:
        stem = norm[: -len(ending)]
        if not norm.endswith(ending) or vowel_count(stem) < 1:
            continue
        for nominative in (stem + "и", stem + "ы"):
            if nominative not in PLURALIA and nominative.replace("е", "ё") not in PLURALIA:
                continue  # помысл-и is a verb: only a noun used in the plural alone
            found = TABLE.variants(nominative)
            if len(found) != 1 or len(found[0][1]) != 1:
                continue  # по́мыслы and помы́слы: no telling which the form keeps
            spelling, (p,) = found[0]
            if p < vowel_count(spelling) - 1:  # the stem's: су́мерки, but not духи́
                return [(spelling[: len(stem)] + ending, (p,))]
    return []


def _lexicon_readings(norm: str) -> list[Reading]:
    options: list[tuple[str, tuple[int, ...], str]] = []
    if norm in CORE:
        options.append((*CORE[norm], "lexicon"))
    else:
        for spelling, stress in TABLE.variants(norm):
            options.append((spelling, stress, "lexicon"))
    if not options and "-" in norm.strip("-"):
        return _hyphenated(norm)
    if not options:
        for spelling, stress in _shift_lookup(norm):
            options.append((spelling, stress, "lexicon"))
    if not options:
        for spelling, stress in _plural_oblique(norm):
            options.append((spelling, stress, "lexicon"))
    if not options:  # дедлайн, фле́ксить: words newer than the table
        for spelling, stress in ru_slang.readings(norm):
            options.append((spelling, stress, "lexicon"))
    if not options:  # Ростова, Алёна: a name the table lacks
        for spelling, stress in ru_names.readings(norm):
            options.append((spelling, stress, "lexicon"))
    elif norm.endswith("ей") and norm not in CORE:
        # the short comparative keeps the stress of its -ее form even where the same
        # spelling is another word: миле́й (милее), not only ми́лей (of miles)
        for _, stress in TABLE.variants(norm[:-2] + "ее"):
            options.append((norm, stress, "lexicon"))
    options = _yo_plural_first(options)
    readings = []
    for spelling, stress, source in options:
        stress = _past_numeral(spelling, _with_last_part(spelling, stress))
        if "-" in spelling and len(stress) > 1 and len({_part_of(spelling, p) for p in stress}) > 1:
            # давны́м-давно́ is stressed in both parts, not in one or the other
            main = max(stress)
            secondary = tuple(p for p in stress if p != main)
            readings.append(Reading(main, transcribe(spelling, main), spelling, source, secondary))
            continue
        for p in stress:
            cost = ALTERNATIVE_COST if readings else 0.0  # the usual reading wins a tie
            readings.append(Reading(p, transcribe(spelling, p), spelling, source, penalty=cost))
    return readings


# Numeral prefixes whose ё the dictionary sometimes gives as the only stress of a
# compound (трЁхцветный): the stem keeps its own (трёхцве́тный, четырёхэта́жный).
NUMERAL_PREFIXES = ("четырёх", "трёх")


def _past_numeral(spelling: str, stress: tuple[int, ...]) -> tuple[int, ...]:
    for prefix in NUMERAL_PREFIXES:
        rest = spelling[len(prefix) :]
        if not spelling.startswith(prefix) or vowel_count(rest) < 1 or "-" in rest[:1]:
            continue
        before = vowel_count(prefix)
        later = tuple(p for p in stress if p >= before)
        if later or not stress:
            return later or stress
        own = TABLE.variants(rest)
        if own:
            return (before + own[0][1][0],)
        guessed = SUFFIXES.order(rest, vowel_count(rest))
        return (before + guessed[0][0],) if guessed else stress
    return stress


# Meter cost of a dictionary reading after the first: enough to settle a tie the
# meter leaves open in favour of the usual reading (уже́ before у́же, е́ду before
# еду́), too little to outweigh a beat.
ALTERNATIVE_COST = 0.1


def _yo_plural_first(
    options: list[tuple[str, tuple[int, ...], str]],
) -> list[tuple[str, tuple[int, ...], str]]:
    """слёзы, the plural, before слезы́, a genitive: where the text's е is ё in a form
    ending in -а, -ы or -и and the е spelling is stressed only on its last vowel
    (звёзды and звезды́, сёстры and сестры́, вёсла and весла́)."""
    if len(options) < 2:
        return options
    e_form, yo_form = options[0], options[1]
    last = vowel_count(e_form[0]) - 1
    if (
        "ё" not in e_form[0]
        and "ё" in yo_form[0]
        and yo_form[0].endswith(("а", "ы", "и"))
        and set(e_form[1]) == {last}
    ):
        return [yo_form, e_form, *options[2:]]
    return options


def _with_last_part(spelling: str, stress: tuple[int, ...]) -> tuple[int, ...]:
    """A hyphenated form the table stresses only before its last part (чёрно-белый,
    whose ё is all the dump marks) gains the last part's own stress: чёрно-бе́лый."""
    parts = spelling.split("-")
    if len(parts) < 2 or parts[-1] in PARTICLES or not vowel_count(parts[-1]):
        return stress
    if any(_part_of(spelling, p) == len(parts) - 1 for p in stress):
        return stress
    tail = analyze_word(parts[-1]).readings
    if not tail or tail[0].stress is None:
        return stress
    return (*stress, vowel_count("".join(parts[:-1])) + tail[0].stress)


def _part_of(spelling: str, vowel: int) -> int:
    """Which hyphenated part of spelling has its vowel number vowel."""
    seen = 0
    for k, part in enumerate(spelling.split("-")):
        seen += vowel_count(part)
        if vowel < seen:
            return k
    return k


# The names of the letters, for an abbreviation sung letter by letter: эс-пэ-бэ́.
LETTER_NAMES = dict(
    zip(
        "абвгдеёжзиклмнопрстуфхцчшщыэюя",
        "а бэ вэ гэ дэ е ё жэ зэ и ка эль эм эн о пэ эр эс тэ у эф ха цэ че ша ща ы э ю я".split(),
    )
)


# Abbreviations said by custom, by the letters each syllable stands for: США is
# сэ-шэ-а́, ЦСКА цэ-эс-ка́.
SPOKEN_ABBREVIATIONS = {"сша": ("сэ", "шэ", "а"), "цска": ("цэ", "эс", "ка")}
# Words with no vowel letter that are sounds, not letters: ХМ, ТСС, БРР.
INTERJECTIONS = set("хм хмм гм мм ммм тс тсс брр бррр шш шшш пс пст псс кх кхм".split())


@cache
def short_words() -> frozenset[str]:
    """Words of one syllable spelt like an abbreviation (two letters, or consonants
    then a vowel: жду, дни, где), which the stress table, holding words of two
    syllables and more, lacks."""
    text = resources.files("ashugh").joinpath("data/ru_short.tsv").read_text(encoding="utf-8")
    return frozenset(text.split())


def letter_names(low: str) -> tuple[str, ...]:
    """What an abbreviation is sung as, syllable by syllable: эс-пэ-бэ́, цэ-эс-ка́."""
    return SPOKEN_ABBREVIATIONS.get(low) or tuple(LETTER_NAMES[ch] for ch in low)


def _a_word(low: str) -> bool:
    """Whether a token in capitals spells a word: СТРАНА, ГДЕ, ВО are no abbreviations."""
    return (
        low.replace("ё", "е") in short_words()
        or low in CLITICS
        or low in CORE
        or bool(TABLE.variants(low))
        or bool(ru_names.readings(low))
        or bool(ru_slang.readings(low))
    )


def _unsayable(low: str) -> bool:
    """No Russian word ends on three consonants the last of them doubled: ГИБДД."""
    run = len(low) - len(low.rstrip("".join(c for c in LETTER_NAMES if c not in VOWELS)))
    return run >= 3 and low[-1] == low[-2]


def abbreviation(token: str, capitals: bool = False) -> Word | None:
    """An abbreviation in capitals sung letter by letter, stressed on the last: СПб,
    МСК, США. One with no vowel letter is always spelt, even in a line all in
    capitals (СССР), unless it is an interjection (ХМ, ТСС); one with a vowel
    when it spells no word and cannot be said as one: it ends on its vowel with
    more consonants (США, МГУ, but ЗАГС, ВУЗ and НАТО are words), has two letters
    (ИП), or ends on a doubled consonant after another (ГИБДД). A line all in
    capitals spells only the last kind and the customary ones (ЦСКА)."""
    if not 2 <= len(token) <= 6 or not token[:2].isupper():
        return None
    low = token.lower()
    if not all(ch in LETTER_NAMES for ch in low) or low in INTERJECTIONS:
        return None
    vowels = vowel_count(low)
    if low not in SPOKEN_ABBREVIATIONS and vowels:
        if _a_word(low):
            return None
        said = low[-1] in VOWELS and vowels < len(low) - vowels or len(low) == 2
        if not _unsayable(low) and (capitals or not said):
            return None
    names = letter_names(low)
    # the letters each syllable stands for: the last takes what is left (Ц-С-КА)
    cuts = [*range(len(names)), len(low)]
    pieces = [token[a:b] for a, b in zip(cuts, cuts[1:])]
    spelling = "".join(names)
    last = len(names) - 1
    return Word(
        text=token,
        norm=low,
        lang=CODE,
        syllables=tuple(Syllable(p) for p in pieces),
        readings=(Reading(last, transcribe(spelling, last), spelling, "lexicon"),),
        spelled=True,
    )


def vocables(words: list[Word]) -> None:
    """A preposition or conjunction said twice in a row is a vocable or an answer,
    not a clitic: на-на-на, да-да-да."""
    for k, w in enumerate(words):
        if w.lang != CODE or not w.clitic:
            continue
        near = [words[j].norm for j in (k - 1, k + 1) if 0 <= j < len(words)]
        if w.norm in near:
            w.clitic = False


def _hyphenated(norm: str) -> list[Reading]:
    """A hyphenated word the table lacks, read part by part: the last stressed
    part carries the stress and the rhyme, the parts before keep theirs as
    secondary stresses (давны́м-давно́, баю́-ба́юшки-баю́); a particle after
    them takes none (кто́-то, когда́-нибудь)."""
    parts = norm.split("-")
    offsets = [vowel_count("".join(parts[:k])) for k in range(len(parts))]
    stresses = []
    spellings = []
    for part in parts:
        if part in PARTICLES or not vowel_count(part):
            stresses.append([])
            spellings.append(part)
        else:  # a part the table lacks is guessed like any word: ба́юшки
            readings = analyze_word(part).readings
            stresses.append([r.stress for r in readings if r.stress is not None])
            spellings.append(readings[0].spelling if readings else part)  # моё, not мое
    stressed = [k for k, options in enumerate(stresses) if options]
    if not stressed:
        return []
    spelling = "-".join(spellings)
    last = stressed[-1]
    secondary = tuple(offsets[k] + stresses[k][0] for k in stressed[:-1])
    readings = []
    for p in dict.fromkeys(stresses[last]):
        at = offsets[last] + p
        readings.append(Reading(at, transcribe(spelling, at), spelling, "lexicon", secondary))
    return readings


def _user_readings(value: str) -> list[Reading]:
    norm, stress = read_marks(value.replace("-", ""))
    if stress is None:
        stress = 0 if vowel_count(norm) == 1 else None
    if stress is None:
        return []
    return [Reading(stress, transcribe(norm, stress), norm, "user")]


# Latin letters that look like Cyrillic ones, as a Latin keyboard types them into
# a Russian word: зáмок with a Latin á, мoре with a Latin o.
LOOK_ALIKE = str.maketrans("aeopcyxAEOPCYXBKMHT", "аеорсухАЕОРСУХВКМНТ")


@cache
def yo_only() -> dict[str, str]:
    """One-syllable words that exist only with ё, by their е spelling: ждет -> ждёт."""
    text = resources.files("ashugh").joinpath("data/ru_yo.tsv").read_text(encoding="utf-8")
    return {w.replace("ё", "е"): w for w in text.split()}


def cyrillic(token: str) -> str:
    """token with Latin look-alike letters made Cyrillic and a precomposed accent
    (á, ó) split into its letter and the stress mark."""
    if token.isascii() or not any(is_cyrillic(ch) for ch in token):
        return token
    decomposed = unicodedata.normalize("NFD", token).translate(LOOK_ALIKE)
    return unicodedata.normalize("NFC", decomposed)  # й and ё again; а + ́ has no single form


def analyze_word(
    token: str, overrides: dict[str, str] | None = None, capitals: bool = False
) -> Word:
    token = APOSTROPHE_MARK.sub("\\1" + ACUTE, cyrillic(token))  # замо'к, as OpenRussian writes
    if not (overrides or {}).get(token.lower()):
        spelled = abbreviation(token, capitals)
        if spelled is not None:
            return spelled
    if lyrics.held_note(token, VOWELS):
        v = token[0].lower()
        return Word(
            text=token,
            norm=token.lower(),
            lang=CODE,
            syllables=(Syllable(token),),
            readings=(Reading(0, transcribe(v, 0), v, "rule"),),
            weak=True,
        )
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
    if marked is not None and not user and _yo_only_mark(token) and n > 1:
        # чёрно-бе́лый, трёхэта́жный: a written ё marks the stress unless the dictionary
        # puts it elsewhere in that very spelling, the ё then a secondary stress
        readings = [r for r in _lexicon_readings(norm) if r.spelling == norm]
        if not readings and "-" in norm.strip("-"):
            readings = _hyphenated(norm)
        marked = None if readings else marked
    if marked is not None:
        readings = [Reading(marked, transcribe(norm, marked), norm, "mark")]
        word.clitic = False
    elif user and not readings:
        readings = _user_readings(user)
    if not readings and n == 0:
        readings = [Reading(None, transcribe(norm, None), norm, "clitic")]
    elif not readings and n == 1:
        # ждет is ждёт: no word is spelled ждет
        yo = None if norm in NOT_YO else yo_only().get(norm) or YO_NAMES.get(norm)
        spellings = [yo] if yo else [norm] + [s for s, _ in TABLE.variants(norm) if s != norm]
        source = "clitic" if clitic else "rule"
        readings = [Reading(0, transcribe(s, 0), s, source) for s in spellings]
    elif not readings:
        readings = _lexicon_readings(norm)
    if not readings and token.isupper() and not capitals and len(token) <= 6:
        # an abbreviation said as a word is stressed on its end: ЕГЭ́, like ОМО́Н
        readings = [Reading(n - 1, transcribe(norm, n - 1), norm, "rule")]
    if not readings:
        readings = [
            Reading(p, transcribe(norm, p), norm, "guess", penalty=cost)
            for p, cost in SUFFIXES.order(norm.replace("-", ""), n)
        ]
        word.notes.append("stress unknown")
    word.readings = tuple(readings)
    return word


PREPOSITIONS = frozenset(
    """в во на по с со к ко у о об обо от ото из изо до за под подо над надо для без при про
    через перед передо между меж сквозь вдоль возле около после вокруг среди из-за
    из-под""".split()
)


def after_prepositions(words: list[Word]) -> None:
    """No verb right after a preposition: по по́лю, not полю́ (I weed); на до́лги."""
    for prev, w in zip(words, words[1:]):
        if w.lang != CODE or prev.norm not in PREPOSITIONS or len(w.readings) < 2:
            continue
        if any(r.source in ("mark", "user") for r in w.readings):
            continue
        kept = [r for r in w.readings if r.stress not in TABLE.verb_only(r.spelling)]
        if kept and kept != list(w.readings):
            w.readings = tuple(
                replace(r, penalty=0.0 if k == 0 else ALTERNATIVE_COST) for k, r in enumerate(kept)
            )


def prefer_names(words: list[Word], starts: list[bool]) -> None:
    """A capitalized word inside a sentence is the name it spells (Ма́шу, Ко́лю, Со́чи,
    not машу́, колю́, сочи́); one that opens a sentence keeps the dictionary's
    reading first and gains the name's (Машу́ рукой, or Ма́шу встретил)."""
    for w, start in zip(words, starts):
        if w.lang != CODE or not w.text[:1].isupper() or w.text.isupper() or w.size < 2:
            continue
        if any(r.source in ("mark", "user") for r in w.readings):
            continue
        names = [
            Reading(p, transcribe(spelling, p), spelling, "lexicon")
            for spelling, stress in ru_names.readings(w.norm)
            for p in stress
        ]
        if not names:
            continue
        if start:
            seen = {(r.spelling, r.stress) for r in w.readings}
            w.readings = (*w.readings, *(n for n in names if (n.spelling, n.stress) not in seen))
        else:
            w.readings = tuple(names)
            if "stress unknown" in w.notes:
                w.notes.remove("stress unknown")


def second_locatives(words: list[Word]) -> None:
    """End-stress the second locative after в, во, на: на берегу́, в крови́; and not
    after a preposition that asks another case: без кра́ю."""
    for prev, w in zip(words, words[1:]):
        if w.lang == CODE and prev.norm in CASE_PREPOSITIONS and w.norm in SECOND_LOCATIVE:
            stem = tuple(r for r in w.readings if r.stress != w.size - 1)
            if stem and w.readings[0].source not in ("mark", "user"):
                w.readings = stem
            continue
        if w.lang != CODE or prev.norm not in LOCATIVE_PREPOSITIONS:
            continue
        if w.norm in LOCATIVE_OR_PLURAL and w.readings[0].source not in ("mark", "user"):
            last = w.size - 1
            end = Reading(last, transcribe(w.norm, last), w.norm, "lexicon")
            w.readings = (end, *(r for r in w.readings if r.stress != last))
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
    for k, w in enumerate(words):  # в э́том дыму́, на то́м берегу́: past the adjectives
        if w.lang != CODE or w.norm not in SECOND_LOCATIVE or w.size < 2:
            continue
        j = k - 1
        # в моей груди́, в ночной тиши́: a feminine noun's adjective ends -ой or -ей
        endings = FEMININE_LOCATIVE_ADJECTIVE if w.norm.endswith("и") else LOCATIVE_ADJECTIVE
        while j >= 0 and k - j <= 2 and words[j].norm.endswith(endings):
            j -= 1
        if j == k - 1 or j < 0 or words[j].norm not in LOCATIVE_PREPOSITIONS:
            continue  # nothing between (done above), or no в or на before them
        if w.readings and w.readings[0].source in ("mark", "user"):
            continue
        last = w.size - 1
        w.readings = (Reading(last, transcribe(w.norm, last), w.norm, "lexicon"),)


# Masculine nouns whose end-stressed form in -а or -я is the nominative plural
# (дома́, леса́), the stem-stressed one the genitive singular a preposition such as у
# or из asks: у до́ма, из ле́са, never у дома́.
PLURAL_IN_A = frozenset(
    """дома леса берега города снега голоса острова луга рога глаза паруса вечера
    поезда тополя номера адреса колокола края века цвета мастера облака бока хлеба
    сорта повара катера доктора профессора директора якоря хутора купола жемчуга""".split()
)
# Feminine nouns the other way round: the genitive singular is stressed on the
# ending (у реки́, из воды́), the plural that is spelt alike on the stem.
GENITIVE_IN_END = frozenset(
    """реки руки ноги горы стены зимы весны воды души земли звезды травы слезы
    головы бороды сестры жены трубы губы доски щеки норы дыры""".split()
)
# Genitives stressed on the end whose stem-stressed form verse uses too: с утра́, but
# гуляли до у́тра; от вина́. The end comes first, the other stays.
GENITIVE_END_FIRST = frozenset({"утра", "вина"})
GENITIVE_PREPOSITIONS = frozenset(
    """у из от до без для около возле после вокруг среди мимо из-за из-под с со ни
    кроме вместо вдоль внутри вне ради против напротив близ""".split()
)


def after_genitive(words: list[Word]) -> None:
    """у до́ма, из ле́са, у реки́, из воды́, из окна́, из села́: no nominative or
    accusative plural after a preposition of the genitive, where a genitive
    singular is spelt like it."""
    for prev, w in zip(words, words[1:]):
        if w.lang != CODE or prev.norm not in GENITIVE_PREPOSITIONS:
            continue
        if w.readings and w.readings[0].source in ("mark", "user"):
            continue
        last = w.size - 1
        if w.norm in PLURAL_IN_A:
            kept = [r for r in w.readings if r.stress != last]
        elif w.norm.replace("ё", "е") in GENITIVE_IN_END:
            kept = [r for r in w.readings if r.stress == last]
        elif w.norm in GENITIVE_END_FIRST:
            kept = sorted(w.readings, key=lambda r: r.stress != last)
        else:  # из окна́, до луны́, из села́: not the plural о́кна, лу́ны, сёла
            kept = [r for r in w.readings if r.stress not in TABLE.plural_only(r.spelling)]
        if kept and kept != list(w.readings):
            w.readings = tuple(
                replace(r, penalty=0.0 if k == 0 else ALTERNATIVE_COST) for k, r in enumerate(kept)
            )


# The locative singular of an adjective or pronoun before a noun: э́том, на́шем, моём.
LOCATIVE_ADJECTIVE = ("ом", "ем", "ём")
FEMININE_LOCATIVE_ADJECTIVE = ("ой", "ей")


def marked_leans(words: list[Word]) -> None:
    """A preposition or не the writer marks takes the stress of what follows: по́
    лесу, за́ руку, не́ был, не́ с кем; the next word up to the first that has a
    stress of its own leans on it."""
    for k, prev in enumerate(words[:-1]):
        if prev.lang != CODE or prev.size != 1 or not prev.readings:
            continue
        if prev.readings[0].source != "mark" or prev.norm not in PREPOSITIONS | {"не", "ни"}:
            continue
        for w in words[k + 1 :]:
            if w.lang != CODE or not w.readings or w.readings[0].source in ("mark", "user"):
                break
            base = w.readings[0]
            w.readings = (Reading(None, transcribe(base.spelling, None), base.spelling, "lean"),)
            if not w.clitic:
                break


def ne_with_pronoun(words: list[Word]) -> None:
    """не́ с кем, не́ о чем, не́ за что: не takes the stress, the preposition and the
    pronoun after it lean on it."""
    for k in range(len(words) - 2):
        ne, prep, pronoun = words[k : k + 3]
        if ne.norm != "не" or prep.norm not in PREPOSITIONS or pronoun.norm not in NE_PRONOUNS:
            continue
        if any(
            w.lang != CODE or w.readings[:1] and w.readings[0].source == "mark"
            for w in (prep, pronoun)
        ):
            continue
        ne.clitic = False
        pronoun.clitic = pronoun.weak = True
        base = pronoun.readings[0] if pronoun.readings else None
        if base is not None:
            pronoun.readings = (
                Reading(None, transcribe(base.spelling, None), base.spelling, "clitic"),
            )


def preposition_shift(words: list[Word]) -> None:
    """Let the noun of a listed pair lend its stress to the preposition: по́ лесу."""
    for prev, w in zip(words, words[1:]):
        if w.lang != CODE or prev.lang != CODE or prev.size != 1 or not prev.clitic:
            continue
        if w.norm not in PREPOSITION_SHIFT.get(prev.norm, ()) or not w.readings:
            continue
        if w.readings[0].source in ("mark", "user"):
            continue
        base = w.readings[0]
        lean = Reading(
            None, transcribe(base.spelling, None), base.spelling, "lean", penalty=LEAN_COST
        )
        if prev.norm == "не" and w.norm in NE_FIRST:  # не́ был: the norm, not a licence
            costly = tuple(replace(r, penalty=max(r.penalty, LEAN_COST)) for r in w.readings)
            w.readings = (replace(lean, penalty=0.0), *costly)
        else:
            w.readings = (*w.readings, lean)
