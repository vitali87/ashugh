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
