"""Russian first names and places, with their stress and their case forms.

The stress table comes from a dictionary of common words, which spells Машу and
Колю only as машу́ (I wave) and колю́ (I chop), and lacks Ростова and Алёна. A
capitalized word inside a sentence is far more often a name, so the line's
analysis puts these readings first there (ru.prefer_names).

Each entry is a lemma with an apostrophe after its stressed vowel (ё needs
none). A first name in -а or -я also gives its possessive (Та́нин) and its
diminutives (Та́нечка, Ни́ночка, Ма́шенька). The forms follow from the ending:
-а/-я decline as feminines (Маша, Машу; Коля, Колю), a consonant, -й and -ь as
masculines (Иван, Ивана; Игорь, Игоря), with ":f" as feminines in -ь (Казань,
Казани) and ":s" as surnames in -ов, -ёв, -ин (Королёв, Королёвым, Королёва,
Королёвой); ":0" does not decline (Сочи); "=" lists the oblique forms of a name
that drops a vowel (Па́вел, Па́вла).
"""

from __future__ import annotations

from functools import cache

VOWELS = "аеёиоуыэюя"

NAMES = """
а'нна а'ня алё'на алёнка алекса'ндра али'на а'лла анастаси'я анже'ла а'ся валенти'на
ва'ля варва'ра ва'ря ве'ра верони'ка ви'ка викто'рия гали'на га'ля да'рья да'ша
евге'ния е'ва екатери'на ка'тя еле'на ле'на елизаве'та ли'за жа'нна зо'я зи'на и'нна
ири'на и'ра ки'ра кристи'на ксе'ния ксю'ша лари'са ле'ся ли'дия ли'да ли'ля лю'ба
людми'ла лю'да ма'йя маргари'та ри'та мари'на мари'я ма'ша ма'ня ми'ла наде'жда на'дя
ната'лья ната'ша ни'на о'льга о'ля поли'на по'ля раи'са светла'на све'та со'фья со'ня
тама'ра татья'на та'ня улья'на ю'лия ю'ля я'на ню'ра фёкла матрё'на
алекса'ндр са'ша са'ня алексе'й лё'ша лё'ха алё'ша анато'лий то'ля андре'й андрю'ша
анто'н арка'дий арсе'ний артё'м тё'ма бори'с бо'ря вади'м валенти'н вале'рий вале'ра
васи'лий ва'ся ви'ктор ви'тя вита'лий влад владисла'в влади'мир во'ва воло'дя
вячесла'в сла'ва генна'дий ге'на гео'ргий го'ша гри'ша григо'рий дании'л да'ня дени'с
дми'трий ди'ма евге'ний же'ня его'р ива'н ва'ня и'горь илья' кири'лл константи'н
ко'стя леони'д лё'ня макси'м матве'й михаи'л ми'ша ники'та никола'й ко'ля оле'г па'ша
пе'тя рома'н ро'ма русла'н семё'н сё'ма серге'й серё'жа станисла'в степа'н стё'па
тимофе'й тиму'р фё'дор фе'дя фили'пп эдуа'рд ю'рий ю'ра я'ков яросла'в кузьма' фома'
лё'ва лука'
па'вел=па'вла па'влу па'влом па'вле
пётр=петра' петру' петро'м петре'
москва' пи'тер петербу'рг новосиби'рск екатеринбу'рг каза'нь:f сама'ра росто'в уфа'
красноя'рск воро'неж волгогра'д краснода'р сара'тов тюме'нь:f иже'вск барнау'л
улья'новск владивосто'к яросла'вль хаба'ровск ирку'тск яку'тск сиби'рь:f ряза'нь:f
со'чи:0 толья'тти:0 тбили'си:0 баку':0 я'лта ки'ев оде'сса ерева'н пари'ж ло'ндон
берли'н ве'на пра'га варша'ва ри'га та'ллин ви'льнюс кавка'з ура'л росси'я аме'рика
евро'па арме'ния гру'зия украи'на ита'лия фра'нция герма'ния испа'ния во'лга нева'
ока' енисе'й ту'ла кострома' во'логда чита' кита'й
горбачёв:s королёв:s хрущёв:s пугачёв:s ковалёв:s соловьёв:s воробьёв:s журавлёв:s
грачёв:s лихачёв:s ткачёв:s
ле'рмонтов:s цвета'ева кура'
оне'гин:s гага'рин:s шаля'пин:s рахма'нинов:s пу'шкин:s есе'нин:s
петро'в:s смирно'в:s ивано'в:s кузнецо'в:s попо'в:s соколо'в:s ле'бедев:s козло'в:s
но'виков:s моро'зов:s во'лков:s васи'льев:s за'йцев:s па'влов:s семё'нов:s го'лубев:s
виногра'дов:s богда'нов:s фё'доров:s миха'йлов:s беля'ев:s тара'сов:s бело'в:s орло'в:s
киселё'в:s мака'ров:s андре'ев:s ильи'н:s гу'сев:s тито'в:s кузьми'н:s бара'нов:s
ку'ликов:s алексе'ев:s степа'нов:s я'ковлев:s соро'кин:s серге'ев:s рома'нов:s заха'ров:s
бори'сов:s гера'симов:s пономарё'в:s григо'рьев:s ла'зарев:s медве'дев:s ершо'в:s
ники'тин:s со'болев:s поляко'в:s цвето'в:s дани'лов:s жу'ков:s фроло'в:s никола'ев:s
крыло'в:s макси'мов:s си'доров:s оси'пов:s белоу'сов:s федо'тов:s его'ров:s ма'твеев:s
бобро'в:s дми'триев:s гро'мов:s бы'ков:s но'сов:s черно'в:s ждано'в:s фоми'н:s купри'н:s
шукши'н:s че'хов:s турге'нев:s некра'сов:s булга'ков:s гончаро'в:s ломоно'сов:s тю'тчев:s
бу'нин:s менделе'ев:s ле'нин:s ста'лин:s проко'фьев:s гребенщико'в:s пу'тин:s
толсто'й:a достое'вский:a маяко'вский:a го'рький:a бро'дский:a высо'цкий:a
чайко'вский:a му'соргский:a ната'ша жуко'вский:a
го'голь пастерна'к окуджа'ва ахма'това шостако'вич
"""


def _stress(entry: str) -> tuple[str, int]:
    seen, yo = 0, None
    for i, ch in enumerate(entry):
        if ch in VOWELS:
            seen += 1
            if entry[i + 1 : i + 2] == "'":
                return entry.replace("'", ""), seen - 1
            if ch == "ё" and yo is None:
                yo = seen - 1
    return entry.replace("'", ""), yo if yo is not None else 0


def _count(text: str) -> int:
    return sum(ch in VOWELS for ch in text)


def _declined(lemma: str, at: int, kind: str) -> list[tuple[str, int]]:
    """The singular case forms of a name, its stress where the lemma has it, or on
    the ending where the lemma's is there (Москва́, Москвы́; Илья́, Ильёй)."""
    if kind == "0":
        return [(lemma, at)]
    last, stem = lemma[-1], lemma[:-1]
    size = _count(lemma)
    if last in "ая":
        on_end = at == size - 1
        if lemma.endswith("ия"):
            endings = ["ия", "ии", "ию", "ией"]
            stem = lemma[:-2]
        elif last == "я":
            endings = ["я", "и", "е", "ю", "ей", "ею"] if not on_end else ["я", "и", "е", "ю", "ёй"]
        else:
            hushing = stem[-1:] in "гкхжшчщ"
            soft_ins = stem[-1:] in "жшчщц" and not on_end
            endings = ["а", "и" if hushing else "ы", "е", "у"]
            endings += ["ей", "ею"] if soft_ins else ["ой", "ою"]
        out = []
        for e in endings:
            form = stem + e
            out.append((form, _count(stem) if on_end else at))
        return out
    if kind == "a":  # Толсто́й, Толсто́го; Достое́вский, Достое́вской: as adjectives
        soft = not lemma.endswith("ой")
        stem = lemma[:-2]
        i = "и" if soft else "ы"
        endings = [lemma[-2:], "ого", "ому", i + "м", "ом", "ая", "ой", "ую", i + "е", i + "х"]
        return [(stem + e, at) for e in endings + [i + "ми"]]
    if kind == "s":  # Королёв, Королёвым; Королёва, Королёвой; Королёвы, Королёвых
        endings = ("", "а", "у", "ым", "е", "ой", "ы", "ых", "ыми")
        return [(lemma + e, at) for e in endings]
    if kind == "f":  # Каза́нь, Каза́ни, Каза́нью
        return [(lemma, at)] + [(stem + e, at) for e in ("и", "ью")]
    if lemma.endswith("ий"):
        stem = lemma[:-2]
        return [(lemma, at)] + [(stem + e, at) for e in ("ия", "ию", "ием", "ии")]
    if last in "йь":
        return [(lemma, at)] + [(stem + e, at) for e in ("я", "ю", "ем", "е")]
    ins = "ем" if last in "жшчщц" else "ом"
    return [(lemma, at)] + [(lemma + e, at) for e in ("а", "у", ins, "е")]


POSSESSIVE = "ин ина ино ины иной иного иному ину иным иных ином иными".split()
DIMINUTIVES = ("ечка", "очка", "енька")


def _kin(lemma: str, at: int) -> list[tuple[str, int]]:
    """A first name's possessive and diminutives, stressed where it is: Та́ня, Та́нин,
    Та́нины, Та́нечка, Та́нечкой; Ни́на, Ни́ночка; Ма́ша, Ма́шенька."""
    if lemma[-1] not in "ая" or lemma.endswith("ия") or at >= _count(lemma) - 1:
        return []
    stem = lemma[:-1]
    out = [(stem + e, at) for e in POSSESSIVE]
    for suffix in DIMINUTIVES:
        out += _declined(stem + suffix, at, "")
    return out


@cache
def forms() -> dict[str, list[tuple[str, tuple[int, ...]]]]:
    """Every form, keyed by its spelling with ё written е: [(spelling, stresses)]."""
    out: dict[str, list[tuple[str, tuple[int, ...]]]] = {}

    def add(spelling: str, at: int) -> None:
        listed = out.setdefault(spelling.replace("ё", "е"), [])
        if (spelling, (at,)) not in listed:
            listed.append((spelling, (at,)))

    for line in NAMES.splitlines():
        if "=" in line:  # a whole line: па́вел=па́вла па́влу па́влом па́вле
            head, _, rest = line.partition("=")
            for form in [head, *rest.split()]:
                add(*_stress(form.strip()))
            continue
        for entry in line.split():
            head, _, kind = entry.partition(":")
            lemma, at = _stress(head)
            if _count(lemma) < 2:
                continue
            for form, stress in _declined(lemma, at, kind) + _kin(lemma, at):
                add(form, stress)
    return out


def readings(norm: str) -> list[tuple[str, tuple[int, ...]]]:
    """The name readings of a form, ё or not: леха is Лёха."""
    return forms().get(norm.replace("ё", "е"), [])
