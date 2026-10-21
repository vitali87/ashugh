"""Russian slang and loanwords of today's songs, with their stress and forms.

The stress table comes from a dictionary that predates тренд, дедлайн and
флексить, so these were guessed, often wrongly (флекси́ть, суперзве́зда). Each
entry is a lemma with an apostrophe after its stressed vowel (ё needs none), as
in ru_names. The forms follow from the ending: a consonant declines as a
masculine noun in both numbers (тре'нд, тре'нда, тре'нды, тре'ндов), -ый as an
adjective (ха'йповый, ха'йповая), -ить as a verb of the second conjugation
(фле'ксить, фле'ксишь, фле'ксил); ":0" does not decline (бе'йби); "=" lists
every form of a word that declines otherwise (суперзвезда́, суперзвёзды).
"""

from __future__ import annotations

from functools import cache

from .ru_names import _stress

SLANG = """
тре'нд фре'нд ха'йп ва'йб дра'йв кри'нж кра'ш стри'м фи'т кли'п ви'дос
хе'йтер рэ'пер панчла'йн зашква'р мейнстри'м стри'мер бло'гер подка'ст хе'штег
га'джет смартфо'н айфо'н дедла'йн звездопа'д трекли'ст плейли'ст фриста'йл зу'мер бу'мер
ха'йповый ва'йбовый тре'ндовый
фле'ксить чи'лить ха'йпить
бе'йби:0 па'ти:0 фло'у:0 бро':0 ло'л:0 и'зи:0
акка'унт
ла'йкать лайкну'ть=лайкни' лайкни'те лайкну' лайкнёшь лайкнёт лайкну'л лайкну'ла
суперзвезда'=суперзвезды' суперзвезде' суперзвезду' суперзвездо'й суперзвёзды
 суперзвёзд суперзвёздам суперзвёздами суперзвёздах
"""

HUSHING = "жшчщ"
VELAR = "гкх"


def _noun(lemma: str, at: int) -> list[tuple[str, int]]:
    """A masculine noun stressed on its stem, in both numbers: тренд, тре́нды."""
    last = lemma[-1]
    plural = "и" if last in HUSHING + VELAR else "ы"
    instrumental = "ем" if last in HUSHING + "ц" else "ом"
    genitive = "ей" if last in HUSHING else "ов"
    endings = ["", "а", "у", instrumental, "е", plural, genitive, "ам", "ами", "ах"]
    return [(lemma + e, at) for e in endings]


ADJECTIVE = "ый ая ое ые ого ому ым ом ой ую ых ыми ою".split()


def _adjective(lemma: str, at: int) -> list[tuple[str, int]]:
    stem = lemma[:-2]
    return [(stem + e, at) for e in ADJECTIVE]


# The consonant of the first person singular: флексить, флекшу; хайпить, хайплю.
MUTATION = {"ст": "щ", "с": "ш", "з": "ж", "т": "ч", "д": "ж"}


def _first_person(stem: str) -> str:
    for before, after in MUTATION.items():
        if stem.endswith(before):
            return stem[: -len(before)] + after + "у"
    return stem + ("л" if stem[-1] in "пбвмф" else "") + "ю"


def _verb(lemma: str, at: int) -> list[tuple[str, int]]:
    """A verb in -ить stressed on its stem: фле́ксить, фле́ксишь, фле́ксил, фле́ксь."""
    stem = lemma[:-3]
    third = "ат" if stem[-1] in HUSHING else "ят"
    forms = [lemma, _first_person(stem)]
    forms += [stem + e for e in ("ишь", "ит", "им", "ите", third, "ил", "ила", "ило", "или")]
    if stem[-1] not in HUSHING:
        forms += [stem + e for e in ("ь", "ьте", "я")]
    return [(f, at) for f in forms]


def _forms_of(lemma: str, at: int, kind: str) -> list[tuple[str, int]]:
    if kind == "0":
        return [(lemma, at)]
    if lemma.endswith("ый"):
        return _adjective(lemma, at)
    if lemma.endswith("ить"):
        return _verb(lemma, at)
    return _noun(lemma, at)


@cache
def forms() -> dict[str, list[tuple[str, tuple[int, ...]]]]:
    """Every form, keyed by its spelling with ё written е: [(spelling, stresses)]."""
    out: dict[str, list[tuple[str, tuple[int, ...]]]] = {}

    def add(spelling: str, at: int) -> None:
        listed = out.setdefault(spelling.replace("ё", "е"), [])
        if (spelling, (at,)) not in listed:
            listed.append((spelling, (at,)))

    text = SLANG.replace("\n ", " ")  # an indented line continues the one before
    for line in text.splitlines():
        if "=" in line:
            head, _, rest = line.partition("=")
            for form in [head, *rest.split()]:
                add(*_stress(form.strip()))
            continue
        for entry in line.split():
            head, _, kind = entry.partition(":")
            lemma, at = _stress(head)
            for form, stress in _forms_of(lemma, at, kind):
                add(form, stress)
    return out


def readings(norm: str) -> list[tuple[str, tuple[int, ...]]]:
    """The slang readings of a form, ё or not: суперзвезды is суперзвезды́ or суперзвёзды."""
    return forms().get(norm.replace("ё", "е"), [])
