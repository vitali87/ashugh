"""Russian as people type it."""

import pytest

from ashugh.lang import ru
from ashugh.scan import scan
from ashugh.spec import from_dict


@pytest.mark.parametrize("token", ["зáмок", "зáмок", "замóк", "мóре"])  # Latin á, a + U+0301, ó
def test_a_latin_accented_vowel_still_counts_and_marks_the_stress(token):
    w = ru.analyze_word(token)
    assert w.size == 2
    assert w.readings[0].source == "mark"


def test_latin_look_alike_letters_inside_a_russian_word_are_read_as_russian():
    assert ru.analyze_word("мoре").size == 2  # Latin o
    assert ru.analyze_word("Мой зáмок стар".split()[1]).readings[0].stress == 0


def test_a_whole_latin_word_is_not_touched():
    from ashugh.lang import script_of

    assert script_of("more") == "en"


@pytest.mark.parametrize("word", ["она", "оно", "они"])
def test_nominative_pronouns_are_weak(word):
    assert ru.analyze_word(word).weak


def test_fets_anapest_scans():
    rep = scan("На заре она сладко так спит\n", from_dict({"language": "ru", "meter": "anapest3"}))
    assert [i for i in rep.issues if i.severity == "error"] == []


@pytest.mark.parametrize(
    "word",
    ["бант", "банта", "банту", "бантом", "банте", "банты", "бантов", "бантам", "бантами", "бантах"],
)
def test_bant_is_stressed_on_the_stem(word):
    assert {r.stress for r in ru.analyze_word(word).readings} == {0}


@pytest.mark.parametrize(
    "plain,yo", [("ждет", "ждёт"), ("шел", "шёл"), ("лед", "лёд"), ("днем", "днём")]
)
def test_a_one_syllable_word_that_exists_only_with_yo_reads_with_it(plain, yo):
    (reading,) = ru.analyze_word(plain).readings
    assert reading.spelling == yo


@pytest.mark.parametrize("word", ["все", "сел", "лет", "нем"])
def test_a_one_syllable_word_that_exists_both_ways_keeps_its_spelling_first(word):
    assert ru.analyze_word(word).readings[0].spelling == word


def test_yo_words_rhyme_and_are_spelled_with_yo_for_suno():
    from ashugh import suno

    rep = scan("Мы пойдём вперед,\nКто нас ждет\n", from_dict({"language": "ru", "rhyme": "AA"}))
    assert not [i for i in rep.issues if i.code == "rhyme"]
    out = suno.format_song("Он ждет меня\n", tags=False).text
    assert out.startswith("Он ждёт")
