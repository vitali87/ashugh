"""Round 13 of dogfooding, Russian: what a songwriter found wrong."""

import pytest

from ashugh import meter, rhyme, suno
from ashugh.lang import ru
from ashugh.scan import analyze_lines, scan
from ashugh.spec import Spec, from_dict


def main_stress(word: str) -> int | None:
    return ru.analyze_word(word).readings[0].stress


@pytest.mark.parametrize(
    "word, stress",
    [
        ("чёрно-белый", 2),
        ("тёмно-синий", 2),
        ("жёлто-синий", 2),
        ("ёлочка-красавица", 4),
        ("трёхэтажный", 2),
        ("трёхцветный", 1),
        ("трехцветный", 1),
        ("четырёхэтажный", 4),
        ("трёхсотый", 1),
        ("трёхколёсный", 2),
        ("зелёный", 1),
        ("самолёт", 2),
    ],
)
def test_a_yo_in_an_earlier_part_is_no_main_stress(word, stress):
    assert main_stress(word) == stress


def rhymes(a: str, b: str) -> float:
    lines = analyze_lines(f"{a}\n{b}", Spec(language="ru"))
    return rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))[0]


@pytest.mark.parametrize("a, b", [("чёрно-белый", "смелый"), ("трёхцветный", "заветный")])
def test_compounds_with_yo_rhyme_on_their_last_part(a, b):
    assert rhymes(a, b) >= rhyme.THRESHOLD["near"]


@pytest.mark.parametrize(
    "line, meter_name",
    [
        ("Ехали по́ лесу долго", "dactyl"),
        ("Я там не́ был", "trochee"),
    ],
)
def test_a_writers_mark_on_a_preposition_or_ne_moves_the_stress(line, meter_name):
    rep = scan(line + "\n", from_dict({"language": "ru", "meter": meter_name}))
    assert rep.ok, [i.message for i in rep.issues]


def test_the_word_after_a_marked_preposition_leans_on_it():
    (ln,) = analyze_lines("Взял её за́ руку", Spec(language="ru"))
    assert [r.stress for r in ln.words[-1].readings] == [None]


@pytest.mark.parametrize("stress, out", [("caps", "зА руку"), ("acute", "за́ руку")])
def test_suno_keeps_a_writers_mark_on_a_preposition(stress, out):
    got = suno.format_song("Взял её за́ руку\n", tags=False, stress=stress).text
    assert out in got


def test_a_stress_the_writer_moved_is_no_ambiguity():
    rep = scan("Ехали по́ лесу долго\n", from_dict({"language": "ru", "meter": "dactyl"}))
    assert not [i for i in rep.issues if i.code == "stress"]


@pytest.mark.parametrize("phrase", ["не был", "не было", "не дал", "не жил"])
def test_ne_takes_the_stress_of_these_verbs_by_default(phrase):
    (ln,) = analyze_lines(phrase, Spec(language="ru"))
    assert ln.words[1].readings[0].stress is None  # не́ был


@pytest.mark.parametrize("phrase", ["не с кем", "не о чем", "не за что", "не к кому"])
def test_ne_before_a_preposition_and_a_pronoun_takes_the_stress(phrase):
    (ln,) = analyze_lines(phrase, Spec(language="ru"))
    f = meter.fit(ln.words, "free")
    assert f.stresses.get(0) == 0 and f.stresses.get(2) is None  # не́ о чем


@pytest.mark.parametrize("a, b", [("не с кем", "резким"), ("Я там не был", "Смотрю на небо")])
def test_ne_stressed_rhymes(a, b):
    assert rhymes(a, b) >= rhyme.THRESHOLD["slant"]


def test_a_word_in_capitals_marks_no_stress():
    (ln,) = analyze_lines("ПЛАТА ЗА ЛЕЧЕНЬЕ", Spec(language="ru"))
    assert ln.words[-1].readings[0].stress == 1


@pytest.mark.parametrize(
    "word, stress",
    [
        ("сумерках", 0),
        ("качелях", 1),
        ("ножницах", 0),
        ("джинсах", 0),
        ("кудрями", 1),
        ("обоих", 1),
        ("обеих", 1),
        ("обоими", 1),
        ("полторы", 2),
        ("полутора", 1),
    ],
)
def test_forms_the_dictionary_lacks(word, stress):
    w = ru.analyze_word(word)
    assert w.readings[0].stress == stress and not w.guessed


def test_perfume_and_spirits_are_both_readings_of_duhov():
    assert {r.stress for r in ru.analyze_word("духов").readings} == {0, 1}
    assert rhymes("твоих духов", "моих стихов") >= rhyme.THRESHOLD["near"]


@pytest.mark.parametrize(
    "phrase", ["в этом дыму", "в нашем саду", "на том берегу", "в густом лесу", "в моём саду"]
)
def test_the_second_locative_is_end_stressed_after_an_adjective_too(phrase):
    (ln,) = analyze_lines(phrase, Spec(language="ru"))
    w = ln.words[-1]
    assert [r.stress for r in w.readings] == [w.size - 1]


def test_a_noun_after_a_noun_in_om_is_left_alone():
    (ln,) = analyze_lines("в доме саду", Spec(language="ru"))
    assert len(ln.words[-1].readings) >= 1 and ln.words[-1].readings[0].source != "rule"


@pytest.mark.parametrize("phrase", ["у дома", "из леса", "до города", "для голоса", "от берега"])
def test_after_a_genitive_preposition_a_plural_in_a_is_no_reading(phrase):
    (ln,) = analyze_lines(phrase, Spec(language="ru"))
    w = ln.words[-1]
    assert w.size - 1 not in {r.stress for r in w.readings}


@pytest.mark.parametrize("phrase", ["из окна", "у моря"])
def test_other_words_after_a_genitive_preposition_keep_their_readings(phrase):
    (ln,) = analyze_lines(phrase, Spec(language="ru"))
    assert ln.words[-1].readings[0].stress == ru.analyze_word(ln.words[-1].text).readings[0].stress


def test_suno_hints_no_stress_the_line_still_fails_with():
    out = suno.format_song(
        "Сижу у дома на скамейке\n",
        tags=False,
        spec=from_dict({"language": "ru", "meter": "trochee"}),
    ).text
    assert "домА" not in out


@pytest.mark.parametrize(
    "phrase", ["у реки", "из воды", "до горы", "для души", "без головы", "от весны"]
)
def test_after_a_genitive_preposition_a_feminine_is_its_genitive(phrase):
    (ln,) = analyze_lines(phrase, Spec(language="ru"))
    w = ln.words[-1]
    assert {r.stress for r in w.readings} == {w.size - 1}


def test_suno_hints_the_usual_reading_in_a_line_that_fails_its_meter():
    spec = from_dict({"language": "ru", "meter": "iamb"})
    out = suno.format_song("Небо синее над рекой\n", tags=False, spec=spec).text
    assert "синЕе" not in out


ROMANCE = (
    "Не уходи, мой свет вечерний,\nЕщё не время расставаться,\n"
    "Пусть будет путь наш самый верный\nХранимым кругом нежных рук.\n"
)


def test_the_partner_that_fails_its_own_slot_is_the_one_blamed():
    rep = scan(ROMANCE, from_dict({"language": "ru", "meter": "iamb4", "rhyme": "AbAb"}))
    broken = [i.line for i in rep.issues if i.code == "rhyme"]
    assert broken == [2]


def test_requests_ask_the_failing_partner_to_rhyme_with_the_good_one():
    from ashugh.fit import requests_for

    reqs = requests_for(ROMANCE, from_dict({"language": "ru", "meter": "iamb4", "rhyme": "AbAb"}))
    by_line = {r.line: r for r in reqs}
    assert by_line[2].rhyme_with == ["рук"]


REFRAIN = (
    "Я помню ночи над рекою,\nСвечу и тени на стене,\n"
    "Как ты, склонившись над рекою,\nШептала что-то в тишине.\n"
)


def test_a_request_for_a_refrain_line_says_why():
    from ashugh.fit import requests_for

    reqs = requests_for(REFRAIN, from_dict({"language": "ru", "meter": "iamb4", "rhyme": "AbAb"}))
    assert any("refrain" in p for r in reqs for p in r.problems)


def test_pick_takes_a_candidate_that_ends_a_refrain():
    from ashugh.fit import fit_song
    from ashugh.proposers import StaticProposer

    proposer = StaticProposer({3: ["Как ты, прильнув ко мне щекою,"]})
    spec = from_dict({"language": "ru", "meter": "iamb4", "rhyme": "AbAb"})
    res = fit_song(REFRAIN, spec, proposer, rounds=1)
    assert res.text.splitlines()[2] == "Как ты, прильнув ко мне щекою,"


def test_a_ternary_line_too_long_for_its_feet_says_so():
    rep = scan(
        "Солнце глядит на нас, как огромное око\n",
        from_dict({"language": "ru", "meter": "dactyl4"}),
    )
    issues = {i.code: i for i in rep.issues if i.severity == "error"}
    assert "syllables" in issues and "has 11" in issues["syllables"].detail
    assert issues["meter"].detail.endswith("dactyl4 wants /xx/xx/xx/x")


def test_a_line_that_fits_its_feet_gets_no_length_error():
    rep = scan("Солнце глядит на огромное око\n", from_dict({"language": "ru", "meter": "dactyl4"}))
    assert rep.ok


@pytest.mark.parametrize(
    "a, b", [("ласковый", "сказочный"), ("ласково", "сказочно"), ("ласковый", "масленый")]
)
def test_dactylic_words_with_the_same_vowels_are_at_least_assonant(a, b):
    assert rhymes(a, b) >= rhyme.THRESHOLD["assonance"]


@pytest.mark.parametrize("a, b", [("ласковый", "ветреный"), ("сказочный", "бешеный")])
def test_dactylic_words_with_other_vowels_are_not(a, b):
    assert rhymes(a, b) < rhyme.THRESHOLD["assonance"]


@pytest.mark.parametrize(
    "word, pieces",
    [
        ("диджей", "ди-джей"),
        ("бюджет", "бю-джет"),
        ("менеджер", "ме-не-джер"),
        ("аджика", "а-джи-ка"),
        ("беззвучный", "без-зву-чный"),
        ("рассвет", "рас-свет"),
        ("касса", "кас-са"),
        ("трёхцветный", "трёх-цве-тный"),
        ("отцвела", "от-цве-ла"),
        ("честных", "чест-ных"),
        ("центра", "цен-тра"),
        ("карта", "кар-та"),
        # negative: под- is a prefix before ж, тв after a cluster stays, пк is no onset
        ("поджечь", "под-жечь"),
        ("надженный", "над-жен-ный"),
        ("чувство", "чувст-во"),
        ("группка", "групп-ка"),
    ],
)
def test_russian_words_are_cut_where_they_are_sung(word, pieces):
    assert "-".join(ru.split_syllables(word)) == pieces


@pytest.mark.parametrize(
    "word, stress",
    [
        ("бейби", 0),
        ("дедлайн", 1),
        ("дедлайны", 1),
        ("флексить", 0),
        ("флексишь", 0),
        ("флекшу", 0),
        ("хайплю", 0),
        ("хайповый", 0),
        ("хайповая", 0),
        ("суперзвезда", 3),
        ("тренде", 0),
        ("френды", 0),
        ("звездопад", 2),
        ("Китай", 1),
        ("Китае", 1),
        ("хейтеры", 0),
        ("кринжем", 0),
        ("зумеры", 0),
    ],
)
def test_slang_and_loanwords_of_songs_are_known(word, stress):
    w = ru.analyze_word(word)
    assert w.readings[0].stress == stress and not w.guessed


def test_a_slang_spelling_shared_by_two_forms_keeps_both():
    w = ru.analyze_word("суперзвезды")
    assert {r.stress for r in w.readings} == {2, 3}
    assert "суперзвёзды" in {r.spelling for r in w.readings}


def test_the_dictionary_still_wins_over_the_slang_table():
    assert [r.stress for r in ru.analyze_word("треку").readings] == [0]  # the table's


def test_suno_marks_a_loanword_where_it_is_said():
    out = suno.format_song("Бейби, ты мой единственный свет\n", tags=False).text
    assert "БейбИ" not in out
