"""Round 10 of dogfooding, Russian: names, abbreviations, vocables, clitics."""

import pytest

from ashugh.lang import analyze, ru, ru_names
from ashugh.lyrics import tokenize
from ashugh.scan import scan
from ashugh.spec import from_dict


def words(line: str):
    return analyze("ru", tokenize(line), {}, line)


def first_stress(line: str, word: str):
    w = next(w for w in words(line) if w.norm == word)
    return w.readings[0].stress, w.readings[0].spelling


@pytest.mark.parametrize(
    "line,word,stress",
    [
        ("Я встретил Машу у реки", "машу", 0),
        ("И Колю звал, и Пашу ждал", "колю", 0),
        ("И Колю звал, и Пашу ждал", "пашу", 0),
        ("Мы едем в Сочи на машине", "сочи", 0),
        ("Онлайн до Ростова едет", "ростова", 1),
        ("Звонила Ире вечерами", "ире", 0),
        ("Мы ждали Илью до утра", "илью", 1),
        ("Я жду Петра у ворот", "петра", 1),
        ("Мы жили в Казани давно", "казани", 1),
        ("Мы ехали к Москве", "москве", 1),
    ],
)
def test_a_capitalized_name_inside_a_line_is_read_as_a_name(line, word, stress):
    assert first_stress(line, word)[0] == stress


@pytest.mark.parametrize(
    "line,word,spelling",
    [("Онлайн до Ростова едет Леха", "леха", "лёха"), ("И Алена ждет меня", "алена", "алёна")],
)
def test_a_name_gets_its_yo(line, word, spelling):
    assert first_stress(line, word) == (1 if word == "алена" else 0, spelling)


def test_a_lowercase_word_keeps_its_dictionary_reading():
    assert first_stress("я машу тебе рукой", "машу")[0] == 1
    assert first_stress("я колю дрова", "колю")[0] == 1


def test_a_name_at_the_start_of_a_line_is_one_reading_among_others():
    w = next(w for w in words("Машу рукой тебе") if w.norm == "машу")
    assert {r.stress for r in w.readings} == {0, 1}
    assert w.readings[0].stress == 1, "the dictionary's reading stays first"


def test_after_a_full_stop_a_capital_starts_a_sentence():
    w = next(w for w in words("Я тут. Машу рукой") if w.norm == "машу")
    assert w.readings[0].stress == 1


def test_names_decline():
    assert ("машей", (0,)) in ru_names.readings("машей")
    assert ru_names.readings("павла") == [("павла", (0,))]
    assert ru_names.readings("ильей") == [("ильёй", (1,))]
    assert ru_names.readings("сочи") and not ru_names.readings("сочах"), "Сочи does not decline"


def test_a_name_inside_a_sentence_is_only_the_name():
    w = next(w for w in words("Мы едем в Сочи на машине") if w.norm == "сочи")
    assert [r.stress for r in w.readings] == [0]
    assert not w.ambiguous


@pytest.mark.parametrize(
    "token,syllables,stress",
    [("СПб", ["С", "П", "б"], 2), ("МСК", ["М", "С", "К"], 2), ("США", ["С", "Ш", "А"], 2)],
)
def test_an_abbreviation_is_sung_letter_by_letter(token, syllables, stress):
    w = next(w for w in words(f"Из {token} опять") if w.text == token)
    assert [s.text for s in w.syllables] == syllables
    assert w.readings[0].stress == stress
    assert not w.guessed


def test_an_abbreviation_read_as_a_word_stays_a_word():
    w = next(w for w in words("Мы шли из ЗАГС домой") if w.text == "ЗАГС")
    assert w.size == 1


def test_a_line_in_capitals_is_not_spelled_out():
    w = next(w for w in words("МЫ ШЛИ ДОМОЙ") if w.text == "ШЛИ")
    assert w.size == 1


def test_the_spelled_letters_count_in_the_line():
    rep = scan("Из СПб в МСК опять\n", from_dict({"language": "ru"}))
    assert rep.lines[0].fit.count == 9


@pytest.mark.parametrize("line", ["На-на-на, да-да-да", "Ла-ла-ла, на-на"])
def test_repeated_vocables_are_not_clitics(line):
    ws = words(line)
    assert all(not w.clitic for w in ws)


def test_a_single_preposition_stays_a_clitic():
    assert next(w for w in words("Иду на реку") if w.norm == "на").clitic


def test_tya_leans_on_the_verb():
    w = next(w for w in words("Люблю тя") if w.norm == "тя")
    assert w.enclitic and w.weak


@pytest.mark.parametrize(
    "token,spelling,main,secondary",
    [
        ("черно-белый", "чёрно-белый", 2, (0,)),
        ("темно-синий", "тёмно-синий", 2, (0,)),
        ("е-мое", "ё-моё", 2, (0,)),
    ],
)
def test_a_hyphenated_word_stresses_its_last_part(token, spelling, main, secondary):
    r = ru.analyze_word(token).readings[0]
    assert (r.spelling, r.stress, r.secondary) == (spelling, main, secondary)


def test_a_compound_yo_is_no_reading_of_its_own():
    assert [r.stress for r in ru.analyze_word("трехэтажный").readings] == [2]


@pytest.mark.parametrize("token,sung", [("черно-белый", "чёр-но-бе-лый"), ("е-мое", "ё-мо-ё")])
def test_a_hyphenated_word_is_sung_with_its_yo(token, sung):
    assert ru.analyze_word(token).sung() == sung


@pytest.mark.parametrize(
    "tag,name",
    [("Инструментал", "Instrumental"), ("Конец", "End"), ("Финал", "Outro"), ("Брейк", "Break")],
)
def test_russian_section_names_become_suno_tags(tag, name):
    from ashugh.lyrics import suno_tag

    assert suno_tag(tag) == name


def test_one_line_and_one_foot_are_singular():
    rep = scan("Я шёл домой\n", from_dict({"language": "ru", "rhyme": "AABB"}))
    assert any("stanza has 1 line," in i.message for i in rep.issues)
    rep = scan("Я шёл\n", from_dict({"language": "ru", "meter": "iamb", "feet": 2}))
    assert any(i.message.startswith("1 foot,") for i in rep.issues)


@pytest.mark.parametrize("word,stress", [("онлайн", 1), ("ваще", 1), ("инстаграм", 2)])
def test_song_slang_is_known(word, stress):
    w = ru.analyze_word(word)
    assert not w.guessed and w.readings[0].stress == stress


def test_sek_keeps_its_e():
    assert ru.analyze_word("сек").readings[0].spelling == "сек"
    assert ru.analyze_word("ждет").readings[0].spelling == "ждёт"


def test_ne_grusti_is_the_verb_first():
    assert first_stress("Не грусти, прошу", "грусти")[0] == 1
