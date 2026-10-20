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
