"""Round 15 of dogfooding, Russian: what a songwriter found wrong."""

import pytest

from ashugh import meter, rhyme, suno
from ashugh.scan import analyze_lines, scan
from ashugh.spec import Spec, from_dict


def line_words(line: str):
    (ln,) = analyze_lines(line, Spec(language="ru"))
    return ln.words


def rhymes(a: str, b: str) -> float:
    lines = analyze_lines(f"{a}\n{b}", Spec(language="ru"))
    return rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))[0]


def sung(text: str, **kw) -> str:
    return suno.format_song(text, tags=False, **kw).text


@pytest.mark.parametrize("a,b", [("сел", "ушёл"), ("лес", "пёс"), ("лет", "полёт")])
def test_a_rare_yo_twin_of_a_short_word_is_no_reading(a, b):
    assert rhymes(a, b) < 0.45


@pytest.mark.parametrize(
    "a,b", [("без слез", "грёз"), ("обо всем", "моём"), ("ну и черт", "упёрт")]
)
def test_a_real_yo_twin_still_rhymes(a, b):
    assert rhymes(a, b) >= 0.9


def test_vse_keeps_both_readings():
    assert {r.spelling for r in line_words("все")[0].readings} == {"все", "всё"}


@pytest.mark.parametrize(
    "text,word",
    [
        ("Прошло так много лет,\nИ вот он, мой полёт.\n", "лет"),
        ("Шумит над нами тёмный лес.\n", "лес"),
    ],
)
def test_suno_leaves_a_short_word_alone(text, word):
    first = sung(text).splitlines()[0]
    assert first == text.splitlines()[0]


@pytest.mark.parametrize(
    "word,stress",
    [
        ("уходя", 2), ("приходя", 2), ("входя", 1), ("отходя", 2), ("нося", 1), ("водя", 1),
        ("ходя", 1), ("летя", 1), ("следя", 1), ("бродя", 1), ("гася", 1), ("возя", 1),
        ("уводя", 2), ("идя", 1), ("неся", 1), ("теряя", 1), ("видя", 0),
    ],
)  # fmt: skip
def test_a_gerund_takes_its_verbs_stress_not_a_nouns(word, stress):
    assert line_words(word)[0].readings[0].stress == stress


def test_pushkin_otkhodya_scans():
    report = scan(
        "Не отходя ни шагу прочь!\n", from_dict({"language": "ru", "meter": "iamb", "feet": 4})
    )
    assert report.lines[0].ok, report.lines[0].issues
