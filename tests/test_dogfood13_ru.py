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
