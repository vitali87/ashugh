"""Round 11 of dogfooding, Russian."""

import pytest

from ashugh.lang import analyze, ru
from ashugh.lyrics import tokenize


def words(line: str):
    return analyze("ru", tokenize(line), {}, line)


def reading(line: str, word: str):
    w = next(w for w in words(line) if w.norm == word)
    return w.readings[0]


def test_the_usual_reading_wins_a_tie():
    from ashugh import suno

    out = suno.format_song("Мне уже всё равно,\nЯ еду к тебе домой,\n", tags=False).text
    assert "ужЕ" in out and "едУ" not in out


@pytest.mark.parametrize("word,first", [("глаза", 1), ("долги", 1), ("уже", 1), ("еду", 0)])
def test_dictionary_order_puts_the_usual_form_first(word, first):
    assert ru.analyze_word(word).readings[0].stress == first


def test_the_plural_with_yo_before_the_genitive():
    assert ru.analyze_word("слезы").readings[0].spelling == "слёзы"


def test_no_verb_after_a_preposition():
    w = next(w for w in words("Иду по полю") if w.norm == "полю")
    assert 1 not in {r.stress for r in w.readings}  # по́лю, or по́ полю; never полю́


def test_a_verb_without_a_preposition_keeps_both():
    w = next(w for w in words("Я полю грядки") if w.norm == "полю")
    assert {r.stress for r in w.readings} == {0, 1}


def test_chem_keeps_its_e():
    assert ru.analyze_word("чем").readings[0].spelling == "чем"


def test_tryokh_gets_its_yo():
    assert ru.analyze_word("трех").readings[0].spelling == "трёх"


@pytest.mark.parametrize("word,spelling", [("зажженные", "зажжённые"), ("сожжен", "сожжён")])
def test_zhech_participles(word, spelling):
    r = ru.analyze_word(word).readings[0]
    assert r.spelling == spelling and r.source == "lexicon"


@pytest.mark.parametrize("word,stress", [("идя", 1), ("ведя", 1), ("неся", 1), ("придя", 1)])
def test_ti_gerunds_are_stressed_on_the_ending(word, stress):
    w = ru.analyze_word(word)
    assert w.readings[0].stress == stress and not w.guessed


@pytest.mark.parametrize(
    "word,stress",
    [("пяти", 1), ("девяти", 2), ("восьми", 1), ("четырьмя", 2), ("пятерых", 2), ("годам", 1)],
)
def test_numerals_and_years(word, stress):
    assert ru.analyze_word(word).readings[0].stress == stress


@pytest.mark.parametrize(
    "line,word,stress",
    [
        ("Где-то Танин тихий дом", "танин", 0),
        ("Я помню Катины глаза", "катины", 0),
        ("Иду гулять с Танечкой", "танечкой", 0),
        ("Привет тебе, моя Ниночка", "ниночка", 0),
        ("Мы ждали Луку", "луку", 1),
    ],
)
def test_name_possessives_and_diminutives(line, word, stress):
    assert reading(line, word).stress == stress


def test_usa_is_se_she_a():
    w = ru.analyze_word("США")
    assert w.readings[0].spelling == "сэшэа"


@pytest.mark.parametrize("a,b", [("класс", "вас"), ("грипп", "скрип")])
def test_a_double_consonant_is_said_single(a, b):
    pa, pb = ru.analyze_word(a).readings[0].phones, ru.analyze_word(b).readings[0].phones
    assert pa[-2:] == pb[-2:]


@pytest.mark.parametrize("tag,name", [("Пре-припев", "Pre-Chorus"), ("Речитатив", "Rap")])
def test_more_russian_tags(tag, name):
    from ashugh.lyrics import suno_tag

    assert suno_tag(tag) == name
