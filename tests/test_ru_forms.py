import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import ru_forms  # noqa: E402


def test_render_marks_the_stressed_vowel_but_not_yo():
    assert ru_forms.render("нежнее", 2) == "нежне'е"
    assert ru_forms.render("решённый", 2) == "решённый"
    assert ru_forms.stress("кре'пче") == ("крепче", 1)
    assert ru_forms.stress("решённый") == ("решённый", 2)
    assert ru_forms.stress("сбить") == ("сбить", None)


# Adjectives: the full declension, its stress fixed where the lemma has it.
@pytest.mark.parametrize(
    "lemma,form",
    [
        ("пре'жний", "пре'жнему"),
        ("пре'жний", "пре'жних"),
        ("пре'жний", "пре'жняя"),
        ("людско'й", "людски'х"),
        ("людско'й", "людска'я"),
        ("люби'мый", "люби'мого"),
        ("ти'хий", "ти'хие"),
        ("хоро'ший", "хоро'шему"),
        ("большо'й", "большо'го"),
        ("большо'й", "больши'е"),
        ("молодо'й", "молоды'х"),
    ],
)
def test_an_adjective_declines(lemma, form):
    assert form in ru_forms.adjective(lemma)


@pytest.mark.parametrize("lemma", ["сбить", "ли'сий", "тре'тий", "ве'тер", "вдвоё'м", ""])
def test_what_is_no_regular_adjective_is_not_declined(lemma):
    assert ru_forms.adjective(lemma) == []


# Comparatives: -ее on the ending after a short feminine stressed there (нежна́),
# on the stem otherwise; -е after a velar or dental stem, on the last stem vowel.
@pytest.mark.parametrize(
    "lemma,short_f,form",
    [
        ("не'жный", "нежна'", "нежне'е"),
        ("бе'лый", "", "беле'е"),  # two syllables: the ending, as nearly always
        ("краси'вый", "краси'ва", "краси'вее"),
        ("преле'стный", "", "преле'стнее"),
        ("надё'жный", "надё'жна", "надёжнее"),
        ("холо'дный", "холодна'", "холодне'е"),
        ("кре'пкий", "крепка'", "кре'пче"),
        ("гро'мкий", "", "гро'мче"),
        ("дорого'й", "", "доро'же"),
        ("ти'хий", "", "ти'ше"),
        ("просто'й", "", "про'ще"),
        ("ре'зкий", "", "ре'зче"),
        ("бли'зкий", "", "бли'же"),
    ],
)
def test_comparatives(lemma, short_f, form):
    assert form in ru_forms.comparatives(lemma, short_f)


def test_a_velar_stem_has_no_comparative_in_ee():
    assert "крепкее" not in {f.replace("'", "") for f in ru_forms.comparatives("кре'пкий", "")}


def test_po_comparatives():
    assert ru_forms.with_po("кре'пче") == "покре'пче"
    assert ru_forms.with_po("нежне'е") == "понежне'е"


# Past passive participles, full and short.
@pytest.mark.parametrize(
    "infinitive,past_m,sg1,sg2,forms",
    [
        ("написа'ть", "написа'л", "напишу'", "напи'шешь", ["напи'санный", "напи'сан", "напи'саны"]),
        ("потеря'ть", "потеря'л", "потеря'ю", "потеря'ешь", ["поте'рянный", "поте'рян"]),
        ("связа'ть", "связа'л", "свяжу'", "сва'жешь", ["свя'занный", "свя'зана"]),
        ("оку'тать", "оку'тал", "оку'таю", "оку'таешь", ["оку'танный", "оку'таны"]),
        ("нарисова'ть", "нарисова'л", "нарису'ю", "нарису'ешь", ["нарисо'ванный"]),
        ("бро'сить", "бро'сил", "бро'шу", "бро'сишь", ["бро'шенный", "бро'шен", "бро'шенных"]),
        ("купи'ть", "купи'л", "куплю'", "ку'пишь", ["ку'пленный", "ку'плен"]),
        ("реши'ть", "реши'л", "решу'", "реши'шь", ["решённый", "решён", "решена'", "решены'"]),
        ("заворожи'ть", "заворожи'л", "заворожу'", "заворожи'шь", ["заворожённый"]),
        ("напо'лнить", "напо'лнил", "напо'лню", "напо'лнишь", ["напо'лненный", "напо'лнен"]),
        ("освободи'ть", "освободи'л", "освобожу'", "освободи'шь", ["освобождённый"]),
        ("сбить", "сби'л", "собью'", "собьёшь", ["сби'тый", "сби'ты", "сби'та"]),
        ("вы'бить", "вы'бил", "вы'бью", "вы'бьешь", ["вы'битый", "вы'бит"]),
        ("забы'ть", "забы'л", "забу'ду", "забу'дешь", ["забы'тый", "забы'т"]),
        ("позабы'ть", "позабы'л", "позабу'ду", "позабу'дешь", ["позабы'тые"]),
        ("обману'ть", "обману'л", "обману'", "обма'нешь", ["обма'нутый", "обма'нутых"]),
        ("дви'нуть", "дви'нул", "дви'ну", "дви'нешь", ["дви'нутый"]),
        ("спасти'", "спа'с", "спасу'", "спасёшь", ["спасённый", "спасён", "спасена'"]),
        ("нести'", "нёс", "несу'", "несёшь", ["несённый"]),
        ("обрести'", "обрёл", "обрету'", "обретёшь", ["обретённый", "обретённых"]),
        ("привезти'", "привёз", "привезу'", "привезёшь", ["привезённый"]),
        ("вы'нести", "вы'нес", "вы'несу", "вы'несешь", ["вы'несенный", "вы'несен"]),
        ("привле'чь", "привлёк", "привлеку'", "привлечёшь", ["привлечённый", "привлечён"]),
        ("сбере'чь", "сберёг", "сберегу'", "сбережёшь", ["сбережённый"]),
        ("обле'чь", "облёк", "облеку'", "облечёшь", ["облечённый"]),
    ],
)
def test_past_passive_participles(infinitive, past_m, sg1, sg2, forms):
    made = ru_forms.past_passive(infinitive, past_m, sg1, sg2)
    for form in forms:
        assert form in made


@pytest.mark.parametrize(
    "infinitive,past_m,sg1,sg2",
    [
        ("взя'ть", "взя'л", "возьму'", "возьмёшь"),  # при́нятый, за́нят: their own pattern
        ("расти'", "ро'с", "расту'", "растёшь"),  # no object, so no passive
        ("вползти'", "вполз", "вползу'", "вползёшь"),
        ("истечь", "истёк", "истеку'", "истечёшь"),
        ("остри'чь", "остри'г", "остригу'", "острижёшь"),  # остри́женный: its own pattern
        ("укра'сть", "укра'л", "украду'", "украдёшь"),  # укра́денный, though украду́
        ("сме'яться", "сме'ялся", "смею'сь", "смеёшься"),  # reflexive: no passive
        ("стере'ть", "стёр", "сотру'", "сотрёшь"),
    ],
)
def test_no_past_passive_participle_where_the_rule_does_not_reach(infinitive, past_m, sg1, sg2):
    assert ru_forms.past_passive(infinitive, past_m, sg1, sg2) == []


@pytest.mark.parametrize(
    "past_m,form",
    [
        ("ста'л", "ста'вший"),
        ("возни'к", "возни'кший"),
        ("поблё'к", "поблёкшей"),
        ("у'мер", "у'мершего"),
        ("улыба'лся", "улыба'вшийся"),
        ("улыба'лся", "улыба'вшимися"),
    ],
)
def test_past_active_participles(past_m, form):
    assert form in ru_forms.past_active(past_m)


# Nouns whose dump row lists no forms: the regular paradigm where the stress
# cannot move.
@pytest.mark.parametrize(
    "lemma,gender,form",
    [
        ("вселе'нная", "f", "вселе'нной"),
        ("мастерска'я", "f", "мастерски'х"),
        ("ко'мната", "f", "ко'мнатами"),
        ("ста'нция", "f", "ста'нциях"),
        ("зда'ние", "n", "зда'нием"),
        ("о'блако", "n", "о'блаком"),
        ("эпата'ж", "m", "эпата'жем"),
        ("почта'рь", "m", "почтаря'"),
        ("почта'рь", "m", "почтарём"),
        ("цвето'к", "m", "цветка'"),
        ("огонё'к", "m", "огонька'"),
        ("бое'ц", "m", "бойца'"),
        ("купе'ц", "m", "купцо'м"),
        ("ге'ний", "m", "ге'ния"),
        ("ге'ний", "m", "ге'ниями"),
        ("судьба'", "f", "судьбо'й"),
    ],
)
def test_noun_paradigms(lemma, gender, form):
    assert form in ru_forms.noun(lemma, gender)


@pytest.mark.parametrize(
    "lemma,gender,absent",
    [
        ("бок", "m", "бока"),  # one syllable: бока́ or бо́ка, the pattern decides
        ("судьба'", "f", "судьбы"),  # су́дьбы or судьбы́: the plural is not derived
        ("вино'", "n", "вина"),  # вина́ or ви́на: the same
        ("гру'дь", "f", "груди"),
    ],
)
def test_noun_forms_left_to_the_dictionary(lemma, gender, absent):
    made = {f.replace("'", "") for f in ru_forms.noun(lemma, gender)}
    assert absent not in made


def test_the_marked_stress_wins_over_an_unstressed_yo():
    assert ru_forms.stress("трёхсо'тый") == ("трёхсотый", 2)


@pytest.mark.parametrize(
    "lemma,short_f,form",
    [
        ("бле'дный", "бле'дна", "бледне'е"),  # one stem syllable: the ending
        ("весё'лый", "весела'", "веселе'е"),
        ("ле'вый", "ле'ва,лева'", "леве'е"),
        ("ви'дный", "ви'дна,видна'", "видне'е"),
    ],
)
def test_comparatives_on_the_ending(lemma, short_f, form):
    assert ru_forms.comparatives(lemma, short_f) == [form]


@pytest.mark.parametrize("infinitive", ["отда'ть", "созда'ть", "проли'ть", "перевить", "собра'ть"])
def test_verbs_of_their_own_participle_pattern_are_left_out(infinitive):
    assert ru_forms.past_passive(infinitive, "", "", "") == []


def test_a_regular_verb_with_a_mobile_looking_end_is_not_left_out():
    assert ru_forms.past_passive("поста'вить", "поста'вил", "поста'влю", "поста'вишь")


@pytest.mark.parametrize(
    "infinitive,form",
    [("распахну'ть", "распа'хнутый"), ("разомкну'ть", "разо'мкнутых"), ("заткну'ть", "за'ткнутый")],
)
def test_nut_verbs_step_their_stress_back(infinitive, form):
    assert form in ru_forms.past_passive(infinitive, "", "", "")


def test_an_unmarked_numeral_compound_is_not_declined():
    assert ru_forms.adjective("трёхсотый") == []
    assert "трёхсо'тая" in ru_forms.adjective("трёхсо'тый")


def test_a_moving_verb_has_both_participles():
    made = ru_forms.past_passive("погрузи'ть", "погрузи'л", "погружу'", "погру'зишь")
    assert made.index("погру'женный") < made.index("погружённый")
    assert "погружена'" in made


def test_a_fixed_ending_verb_has_only_the_one():
    made = ru_forms.past_passive("отключи'ть", "отключи'л", "отключу'", "отключи'шь")
    assert "отключённый" in made and "отклю'ченный" not in made


def test_past_active_follows_the_infinitive_after_a_vowel():
    assert "созда'вший" in ru_forms.past_active("со'здал", "созда'ть")
    assert "поня'вшими" in ru_forms.past_active("по'нял", "поня'ть")
    assert "возни'кший" in ru_forms.past_active("возни'к", "возни'кнуть")
    assert "улыба'вшимися" in ru_forms.past_active("улыба'лся", "улыба'ться")


@pytest.mark.parametrize(
    "infinitive,form",
    [
        ("припаркова'ть", "припарку'ет"),
        ("припаркова'ть", "припарку'ют"),
        ("припаркова'ть", "припарку'й"),
        ("финанси'ровать", "финанси'рует"),
        ("финанси'роваться", "финанси'руются"),
        ("зафрахто'вывать", "зафрахто'вывает"),
        ("сосредота'чивать", "сосредота'чиваю"),
        ("переформиро'вывать", "переформиро'вываем"),
    ],
)
def test_present_of_regular_suffixed_verbs(infinitive, form):
    assert form in ru_forms.present(infinitive)


@pytest.mark.parametrize("infinitive", ["кова'ть", "сосна'ть", "писа'ть", "сиде'ть", "плева'ть"])
def test_no_present_where_the_suffix_is_the_root(infinitive):
    assert ru_forms.present(infinitive) == []


@pytest.mark.parametrize(
    "infinitive,forms",
    [
        ("заже'чь", ["зажжённый", "зажжённые", "зажжён", "зажжена'"]),
        ("сже'чь", ["сожжённый", "сожжён"]),
        ("подже'чь", ["подожжённый"]),
        ("вы'жечь", ["вы'жженный", "вы'жжен"]),
    ],
)
def test_burnt_participles(infinitive, forms):
    made = ru_forms.past_passive(infinitive, "", "", "")
    for form in forms:
        assert form in made
