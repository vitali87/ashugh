"""Regular Russian forms the OpenRussian dump leaves out, derived from its lemmas.

Forms are written as the dump writes them: an apostrophe after the stressed vowel,
none after ё, which is always stressed. The builder adds a derived form only where
the dump lists no form with that spelling, so a derivation fills a gap and never
overrules the dictionary. Each rule covers a regular class and declines whatever
it cannot place (a one-syllable noun, whose stress may move to any ending; the
plural of a noun stressed on its ending; a verb of its own pattern).
"""

from __future__ import annotations

VOWELS = "аеёиоуыэюя"
VELARS = "гкх"
SIBILANTS = "жшчщ"


def count(text: str) -> int:
    return sum(ch in VOWELS for ch in text)


def stress(form: str) -> tuple[str, int | None]:
    """The bare spelling and the 1-based position of its stressed vowel: the first
    marked one, or else the ё (трёхсо́тый marks its stress past the ё)."""
    seen, yo = 0, None
    for i, ch in enumerate(form):
        if ch in VOWELS:
            seen += 1
            if form[i + 1 : i + 2] == "'":
                return form.replace("'", ""), seen
            if ch == "ё" and yo is None:
                yo = seen
    return form.replace("'", ""), yo


def render(bare: str, at: int, keep_yo: bool = False) -> str:
    """bare stressed on its vowel at: an apostrophe after it, unless it is ё; an ё
    the stress has left becomes е (весёлый, веселе́е) unless keep_yo, where it
    belongs to the word's first part (трёхсо́тый)."""
    out, seen = [], 0
    for ch in bare:
        if ch in VOWELS:
            seen += 1
            if ch == "ё" and seen != at and not keep_yo:
                ch = "е"
            out.append(ch)
            if seen == at and ch != "ё":
                out.append("'")
        else:
            out.append(ch)
    return "".join(out)


def _unmarked_compound(lemma: str) -> bool:
    """трёхсотый with no mark: its ё is the first part's, not the word's stress."""
    return "'" not in lemma and lemma.startswith(("трёх", "четырёх", "двух"))


def _first(variants: str) -> str:
    return variants.replace(";", ",").split(",")[0].strip().lower()


# Adjective endings, nominative masculine first.
HARD = "ый ого ому ым ом ая ой ую ою ое ые ых ыми".split()
HARD_END = "ой ого ому ым ом ая ую ою ое ые ых ыми".split()
VELAR = "ий ого ому им ом ая ой ую ою ое ие их ими".split()
VELAR_END = "ой ого ому им ом ая ую ою ое ие их ими".split()
SIBILANT = "ий его ему им ем ая ей ую ею ее ие их ими".split()
SOFT = "ий его ему им ем яя ей юю ею ее ие их ими".split()


def adjective(lemma: str) -> list[str]:
    """The declension of a regular adjective, stressed where its lemma is: пре́жний,
    пре́жнему; людско́й, людски́х."""
    bare, at = stress(_first(lemma))
    if at is None or "-" in bare or len(bare) < 4 or _unmarked_compound(lemma):
        return []
    stem, end = bare[:-2], bare[-2:]
    last = stem[-1:]
    if end not in ("ый", "ий", "ой") or not count(stem) or not last or last in VOWELS + "ьй":
        return []
    on_end = at > count(stem)
    if end == "ой":
        if not on_end:
            return []
        table = VELAR_END if last in VELARS + SIBILANTS else HARD_END
    elif on_end:
        return []
    elif end == "ий":
        table = VELAR if last in VELARS else SIBILANT if last in SIBILANTS else SOFT
        if last not in VELARS + SIBILANTS + "н":
            return []  # ли́сий, тре́тий: their own declension
    else:
        if last in VELARS + SIBILANTS + "ц":
            return []
        table = HARD
    return [render(stem + e, at, keep_yo=True) for e in table]


# The consonant a comparative in -е takes: кре́пкий, кре́пче; бли́зкий, бли́же (but
# ре́зкий, ре́зче: both are made, and the dictionary's own forms win).
ALTERNATIONS = {
    "ск": ("щ",),
    "ст": ("щ",),
    "зк": ("ж", "зч"),
    "г": ("ж",),
    "к": ("ч",),
    "х": ("ш",),
    "д": ("ж",),
    "т": ("ч",),
}
# Comparatives no rule reaches, as the standard language has them; уже is left out,
# for уже́ (already) is the common word.
IRREGULAR_COMPARATIVES = (
    "бо'льше ме'ньше лу'чше ху'же до'льше да'льше то'ньше го'рше сла'ще ме'льче по'зже "
    "ра'ньше глу'бже ши'ре вы'ше ни'же бли'же ре'же ста'рше мла'дше то'лще жё'стче ле'гче "
    "коро'че у'же"
).split()[:-1]


def comparatives(lemma: str, short_f: str = "") -> list[str]:
    """The comparatives of a qualitative adjective: -ее, stressed on its ending where
    the short feminine is (нежна́, нежне́е) and on the stem otherwise (краси́ва,
    краси́вее); -е after a velar or dental stem, on the last stem vowel (кре́пче)."""
    bare, at = stress(_first(lemma))
    if at is None or "-" in bare:
        return []
    stem, end = bare[:-2], bare[-2:]
    last = stem[-1:]
    if end not in ("ый", "ий", "ой") or not count(stem) or not last or last in VOWELS + "ьй":
        return []
    velar = last in VELARS
    if end == "ий" and not velar:
        return []  # си́ний, хоро́ший: no comparative to derive
    size = count(stem)
    out: list[str] = []
    if not velar:
        variants = [stress(v.strip()) for v in short_f.replace(";", ",").split(",") if v.strip()]
        on_end = any(a == count(b) and b.endswith("а") for b, a in variants)
        stem_at = next((a for b, a in variants if a is not None and a < count(b)), None)
        if on_end or size == 1 or at > size:
            place = size + 1  # нежна́, нежне́е; бле́дный, бледне́е
        else:
            place = stem_at or at  # краси́ва, краси́вее
        out.append(render(stem + "ее", place))
    suffix = next((s for s in sorted(ALTERNATIONS, key=len, reverse=True) if stem.endswith(s)), "")
    if suffix and (velar or suffix in ("д", "т", "ст")):
        for new in ALTERNATIONS[suffix]:
            form = stem[: -len(suffix)] + new + "е"
            out.append(render(form, count(form) - 1))
    return list(dict.fromkeys(out))


def with_po(form: str) -> str:
    """The comparative with по-: покре́пче, понежне́е."""
    bare, at = stress(form)
    return render("по" + bare, (at or 0) + 1)


def _short(stem: str, at: int, end_stressed: bool = False) -> list[str]:
    if end_stressed:  # решён, решена́, решено́, решены́
        size = count(stem)
        return [render(stem + "ён", size + 1)] + [
            render(stem + e, size + 2) for e in ("ена", "ено", "ены")
        ]
    return [render(stem + e, at) for e in ("", "а", "о", "ы")]


# Verb roots whose participles move their stress in their own way (о́тдан, отдана́;
# про́лит, пролита́, пролито́й; со́бран, собрана́): left to the runtime's guess.
MOBILE_ROOTS = {
    "дать", "лить", "вить", "пить", "брать", "звать", "гнать", "рвать", "драть", "ткать",
    "жить", "спать", "ждать", "лгать", "врать", "слать",
}  # fmt: skip
VERB_PREFIXES = sorted(
    "пере пред при про пре разо раз рас без бес взо воз вос вз вс изо из ис недо надо над "
    "подо под обо об ото от по до за на со соз с у о во в вы ни нис".split(),
    key=len,
    reverse=True,
)


# Roots of -сти, -зти and -чь verbs with no object, so no passive: врасти, вползти, вытечь;
# not брести or лечь, which обрести and облечь would match.
INTRANSITIVE_ROOTS = {"расти", "ползти", "цвести", "лезти", "течь", "мочь"}


def _mobile(infinitive: str, roots: set[str] = MOBILE_ROOTS) -> bool:
    if infinitive in roots:
        return True
    return any(
        infinitive.startswith(p) and _mobile(infinitive[len(p) :], roots)
        for p in VERB_PREFIXES
        if len(infinitive) > len(p)
    )


def past_passive(infinitive: str, past_m: str, sg1: str, sg2: str) -> list[str]:
    """The past passive participle, full and short: напи́санный, напи́сан; бро́шенный;
    решённый, решена́; сби́тый, сби́ты; спасённый, привлечённый, вы́несенный. Verbs
    of their own pattern (взять, при́нятый; отдать, отдана́; остричь, остри́женный),
    reflexive verbs, -сть and -ереть verbs give none."""
    inf, at = stress(_first(infinitive))
    if not inf or inf.endswith(("ся", "сь")) or _mobile(inf):
        return []
    if inf.endswith("жечь"):
        return _burnt(inf[:-4])
    if at is None:
        at = 1 if count(inf) == 1 else stress(_first(past_m))[1]
    if at is None:
        return []
    first = stress(_first(sg1))[0]
    second, at2 = stress(_first(sg2))
    size = count(inf)
    if inf.endswith(("ать", "ять")):
        if first.endswith(("му", "ну")):
            return []  # взять, начать, понять: при́нятый, на́чатый
        stem = inf[:-2]
        place = at - 1 if at == size and size > 1 else at
        return adjective(render(stem + "нный", place)) + _short(stem + "н", place)
    if inf.endswith(("ить", "еть")) and first.endswith(("у", "ю")) and second.endswith("ишь"):
        stems = [first[:-1]]
        if stems[0].endswith("ж") and inf[:-3].endswith("д"):
            stems.append(stems[0] + "д")  # освободи́ть, освобождённый
        if inf.endswith("еть"):
            stems.append(inf[:-3])  # уви́деть, уви́денный
        out: list[str] = []
        moving = stress(_first(sg1))[1] == count(first)  # куплю́ but ку́пишь
        for stem in stems:
            on_end = adjective(render(stem + "ённый", count(stem) + 1))
            on_end += _short(stem, 0, end_stressed=True)
            if at2 is not None and at2 == count(second):
                out += on_end  # реши́шь: решённый
            elif at2 is not None and at2 <= count(stem):
                # ку́пишь: ку́пленный; a verb with куплю́ beside it may also have
                # the ending's (погру́женный and погружённый)
                out += adjective(render(stem + "енный", at2)) + _short(stem + "ен", at2)
                out += on_end if moving else []
        return out
    mono_root = inf.endswith("ить") and first.endswith(("ью", "ию"))
    if inf.endswith(("ыть", "уть")) or mono_root:
        stem = inf[:-2]
        # обману́ть, обма́нутый; распахну́ть, распа́хнутый: the stress steps back
        place = at - 1 if inf.endswith("уть") and at == size and size > 1 else at
        return adjective(render(stem + "тый", place)) + _short(stem + "т", place)
    if inf.endswith(("сти", "зти", "чь")) and not _mobile(inf, INTRANSITIVE_ROOTS | {"стричь"}):
        stem, at1 = stress(_first(sg1))
        if not stem.endswith(("у", "ю")) or at1 is None:
            return []
        stem = stem[:-1]
        if inf.endswith("чь"):  # привлеку́, привлечённый; сберегу́, сбережённый
            stem = stem[:-1] + {"к": "ч", "г": "ж"}.get(stem[-1], stem[-1])
        if at1 == count(stem) + 1:  # спасу́: спасённый, спасён, спасена́
            return adjective(render(stem + "ённый", at1)) + _short(stem, 0, end_stressed=True)
        return adjective(render(stem + "енный", at1)) + _short(stem + "ен", at1)  # вы́несу
    return []


def _burnt(prefix: str) -> list[str]:
    """The participle of жечь and its compounds: зажжённый, зажжён, зажжена́;
    сожжённый and подожжённый (a consonant prefix takes о); вы́жженный."""
    if prefix == "вы":
        return adjective("вы'жженный") + _short("выжжен", 1)
    if prefix and prefix[-1] not in VOWELS:
        prefix += "о"
    stem = prefix + "жж"
    return adjective(render(stem + "ённый", count(stem) + 1)) + _short(stem, 0, end_stressed=True)


def past_active(past_m: str, infinitive: str = "") -> list[str]:
    """The past active participle: stressed as the infinitive after a vowel (созда́ть,
    созда́вший, though со́здал), as the past otherwise (возни́к, возни́кший);
    улыба́лся, улыба́вшийся."""
    bare, at = stress(_first(past_m))
    inf, inf_at = stress(_first(infinitive))
    if inf_at is None and count(inf) == 1:
        inf_at = 1
    in_l = bare.removesuffix("ся").removesuffix("сь").endswith("л")
    for tail, reflexive in (("ться", True), ("ть", False)):
        stem = inf[: -len(tail)]
        if in_l and inf_at is not None and inf.endswith(tail) and stem[-1:] in VOWELS:
            forms = adjective(render(stem + "вший", inf_at))
            return [f + "ся" for f in forms] if reflexive else forms
    if at is None and count(bare) == 1:
        at = 1
    if at is None:
        return []
    reflexive = bare.endswith(("ся", "сь"))
    base = bare[:-2] if reflexive else bare
    if base.endswith("л"):
        stem = base[:-1] + "вш"
    elif base and base[-1] not in VOWELS + "ь":
        stem = base + "ш"
    else:
        return []
    forms = adjective(render(stem + "ий", at))
    return [f + "ся" for f in forms] if reflexive else forms


def _hard(stem: str, ending: str) -> str:
    """A noun ending after its stem's last consonant: ы is и after a velar or a
    sibilant (кни́ги), an unstressed о is е after a sibilant or ц (эпата́жем)."""
    last = stem[-1:]
    if ending.startswith("ы") and last in VELARS + SIBILANTS:
        ending = "и" + ending[1:]
    return ending


def noun(lemma: str, gender: str) -> list[str]:
    """The forms of a noun whose stress the paradigm cannot move: an adjectival noun
    (вселе́нная), a noun stressed on its stem (ко́мната, зда́ние), and the singular of
    one stressed on its ending (судьбе́, судьбо́й); masculine nouns in -а́рь and with a
    fleeting vowel (цвето́к, цветка́) are stressed on every ending."""
    bare, at = stress(_first(lemma))
    if at is None or count(bare) < 2 or "-" in bare:
        return []
    size = count(bare)
    adjectival = _adjectival(bare, at)
    if adjectival is not None:
        return adjective(adjectival)
    last = bare[-1]
    if last in "ая" and gender in ("f", "m", ""):
        return _first_declension(bare, at, size)
    if last in "ое" and gender in ("n", ""):
        return _neuter(bare, at, size)
    if gender == "f" and last == "ь":
        stem = bare[:-1]
        if at == size:
            return []
        out = [render(stem + e, at) for e in ("и", "ью")]
        if bare.endswith(("ость", "есть")):
            out += [render(stem + e, at) for e in ("ей", "ям", "ями", "ях")]
        return out
    if gender in ("m", ""):
        return _masculine(bare, at, size)
    return []


def _adjectival(bare: str, at: int) -> str | None:
    """The masculine lemma of a noun declined as an adjective (вселе́нная, мастерска́я,
    рабо́чий), or None."""
    stem, end = bare[:-2], bare[-2:]
    if not stem or stem[-1] in VOWELS + "ьй":
        return None
    on_end = at > count(stem)
    last = stem[-1]
    if end in ("ая", "ое"):
        if on_end:
            return render(stem + "ой", at)
        return render(stem + ("ий" if last in VELARS + SIBILANTS else "ый"), at)
    if end in ("яя", "ее") and not on_end:
        return render(stem + "ий", at)
    if end == "ий" and last in SIBILANTS and not on_end:
        return render(stem + "ий", at)
    if end == "ый" and not on_end:
        return render(bare, at)
    return None


def _first_declension(bare: str, at: int, size: int) -> list[str]:
    if bare.endswith("ия"):
        stem = bare[:-2]
        if at > count(stem):
            return []
        return [render(stem + e, at) for e in ("ии", "ию", "ией", "ий", "иям", "иями", "иях")]
    stem, soft = bare[:-1], bare.endswith("я")
    if at == size:
        # судьба́: судьбе́, судьбо́й, but not the genitive, which the plural may share
        # (су́дьбы), nor the accusative, which may take the stress back (зи́му)
        ins = "ёй" if soft else "ой"
        return [render(stem + e, at) for e in ("е", ins)]
    if soft:
        endings = ("и", "е", "ю", "ей", "ям", "ями", "ях")
    else:
        ins = "ей" if stem[-1:] in SIBILANTS + "ц" else "ой"
        endings = (_hard(stem, "ы"), "е", "у", ins, "ам", "ами", "ах")
    return [render(stem + e, at) for e in endings]


def _neuter(bare: str, at: int, size: int) -> list[str]:
    if bare.endswith("ие"):
        stem = bare[:-2]
        if at > count(stem):
            return []
        return [render(stem + e, at) for e in ("ия", "ию", "ием", "ии", "ий", "иям", "иями", "иях")]
    stem = bare[:-1]
    if bare.endswith("мя"):
        return []
    if at == size:  # вино́: вину́, вино́м, вине́, but not вина, which ви́на shares
        return [render(stem + e, at) for e in ("у", "ом", "е")]
    # о́блако: the singular but its genitive (облака́, the plural, is spelt the same)
    if bare.endswith("о"):
        ins = "ем" if stem[-1:] in SIBILANTS + "ц" else "ом"
        return [render(stem + e, at) for e in ("у", ins, "е")]
    return [render(stem + e, at) for e in ("ю", "ем")]


# Final-stressed masculine nouns borrowed with their stress, which stays on the stem
# (эпата́ж, эпата́жа); native ones often move it to the ending (язы́к, языка́).
LOAN_ENDINGS = ("аж", "ист", "изм", "ент", "ант", "ат", "ер")


def _masculine(bare: str, at: int, size: int) -> list[str]:
    last = bare[-1]
    if last == "й":
        if bare.endswith("ей") or bare[-2:-1] not in VOWELS:
            return []  # руче́й, ручья́: a fleeting е
        if bare.endswith("ий"):
            stem = bare[:-2]
            if at > count(stem):
                return []
            return [
                render(stem + e, at) for e in ("ия", "ию", "ием", "ии", "иев", "иям", "иями", "иях")
            ]
        stem = bare[:-1]
        return [render(stem + e, at) for e in ("я", "ю", "ем", "е", "и", "ев", "ям", "ями", "ях")]
    if last == "ь":
        stem = bare[:-1]
        if bare.endswith(("арь", "ярь")) and at == size:
            return [
                render(stem + e, size + 1)
                for e in ("я", "ю", "ём", "е", "и", "ей", "ям", "ями", "ях")
            ]
        if at == size or bare.endswith(("ень", "ель")):
            return []
        return [render(stem + e, at) for e in ("я", "ю", "ем", "е", "и", "ей", "ям", "ями", "ях")]
    if last in VOWELS:
        return []
    if at == size:
        fleeting = _fleeting(bare)
        if fleeting is not None:
            stem = fleeting
            plural = "ы" if stem.endswith("ц") else "и"
            return [
                render(stem + e, count(stem) + 1)
                for e in ("а", "у", "ом", "е", plural, "ов", "ам", "ами", "ах")
            ]
        if not bare.endswith(LOAN_ENDINGS) or bare.endswith(("ёр", "ер")) and "ё" in bare:
            return []
    elif bare.endswith(("ок", "ек", "ец", "ёк", "ен", "ел", "ер", "ор", "ол")):
        return []  # a fleeting vowel or a plural in -а́ may be hiding
    stem = bare
    sibilant = last in SIBILANTS
    ins = "ем" if (sibilant or last == "ц") and at <= count(stem) else "ом"
    gen_pl = "ей" if sibilant else ("ев" if last == "ц" else "ов")
    endings = ("а", "у", ins, "е", _hard(stem, "ы"), gen_pl, "ам", "ами", "ах")
    if size == 2 and at < size:
        endings = endings[1:]  # го́рода or города́: a genitive the plural may share
    return [render(stem + e, at) for e in endings]


def _fleeting(bare: str) -> str | None:
    """The oblique stem of a masculine noun whose last vowel drops: цвето́к, цветк-;
    огонёк, огоньк-; бое́ц, бойц-; купе́ц, купц-."""
    if bare.endswith("ок") and bare[-3:-2] not in VOWELS:
        return bare[:-2] + "к"
    if bare.endswith("ёк"):
        return bare[:-2] + ("йк" if bare[-3:-2] in VOWELS else "ьк")
    if bare.endswith("ец"):
        before = bare[-3:-2]
        return bare[:-2] + ("йц" if before in VOWELS else "ьц" if before == "л" else "ц")
    return None


def present(infinitive: str) -> list[str]:
    """The present tense, imperative and gerund of a verb in -овать (припаркова́ть,
    припарку́ет; финанси́ровать, финанси́рует) or -ывать/-ивать (зафрахто́вывать,
    зафрахто́вывает), which conjugate without exception. A root that is all the
    suffix (кова́ть, плева́ть) has its own present (кую́, плюю́)."""
    inf, at = stress(_first(infinitive))
    reflexive = inf.endswith("ся")
    base = inf[:-2] if reflexive else inf
    if at is None:
        return []
    if base.endswith("овать") and count(base[:-5]) >= 1 and len(base) > 7:
        stem = base[:-5]
        place = count(stem) + 1 if at > count(stem) else at  # -ова́ть: -у́ю
        endings = ("ую", "уешь", "ует", "уем", "уете", "уют", "уй", "уйте", "уя")
        forms = [render(stem + e, place) for e in endings]
    elif base.endswith(("ывать", "ивать")) and count(base) >= 4:
        stem = base[:-2]
        endings = ("ю", "ешь", "ет", "ем", "ете", "ют", "й", "йте", "я")
        forms = [render(stem + e, at) for e in endings]
    else:
        return []
    if reflexive:
        forms = [f + ("сь" if f.replace("'", "")[-1] in VOWELS else "ся") for f in forms]
    return forms
