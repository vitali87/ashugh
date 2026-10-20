"""A hyphenated word the dictionary lacks: each part keeps its stress, the last one rhymes."""

import pytest

from ashugh import meter, rhyme
from ashugh.lang import en, ru
from ashugh.scan import analyze_lines
from ashugh.spec import Spec


def score(a: str, b: str, lang: str) -> float:
    lines = analyze_lines(f"{a}\n{b}", Spec(language=lang), lang)
    return rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))[0]


@pytest.mark.parametrize(
    "word,main,others",
    [("баю-баюшки-баю", 6, {1, 2}), ("туда-сюда", 3, {1}), ("давным-давно", 3, {1})],
)
def test_russian_parts_keep_their_stresses(word, main, others):
    (r,) = ru.analyze_word(word).readings
    assert r.stress == main and others <= set(r.secondary)


def test_a_russian_particle_part_stays_unstressed():
    assert ru.analyze_word("кто-то").stress_options() == [0]
    assert ru.analyze_word("когда-нибудь").stress_options() == [1]


def test_the_last_russian_part_carries_the_rhyme():
    assert score("Баю-баюшки-баю", "Песню тихую пою", "ru") >= rhyme.THRESHOLD["perfect"]


@pytest.mark.parametrize(
    "word,size,main,others",
    [
        ("ice-cold", 2, 1, {0}),
        ("bone-dry", 2, 1, {0}),
        ("slow-motion", 3, 1, {0}),
        ("twenty-four-seven", 5, 3, {0, 2}),
        ("whoa-oh", 2, 1, {0}),
        ("mm-hmm", 2, 1, {0}),
    ],
)
def test_english_parts_keep_their_stresses(word, size, main, others):
    w = en.analyze_word(word)
    r = w.readings[0]
    assert w.size == size and r.stress == main and others <= set(r.secondary)
    assert not w.guessed or word == "mm-hmm"  # a vocable no dictionary lists


@pytest.mark.parametrize(
    "a,b",
    [("ice-cold", "gold"), ("bone-dry", "sky"), ("self-made", "fade"), ("slow-motion", "ocean")],
)
def test_the_last_english_part_carries_the_rhyme(a, b):
    assert score(f"it was {a}", f"under the {b}", "en") >= rhyme.THRESHOLD["perfect"]


def test_a_clitic_part_takes_no_stress():
    r = en.analyze_word("up-to-date").readings[0]
    assert r.stress == 2 and 1 not in r.secondary


def test_a_hyperdactylic_slot_takes_three_or_more_after_the_stress():
    from ashugh.scan import scan
    from ashugh.spec import from_dict

    line = "Эти высказывания\n"
    assert scan(line, from_dict({"language": "ru", "endings": "h"})).ok  # вы́-ска-зы-ва-ни-я
    assert not scan(line, from_dict({"language": "ru", "endings": "d"})).ok


@pytest.mark.parametrize(
    "line,spec",
    [
        ("Kiss me goodbye at the closing-time bell", {"meter": "dactyl"}),
        ("The long-lost lover comes back home", {"meter": "iamb4"}),
    ],
)
def test_a_hyphenated_word_may_stress_its_first_part_where_the_meter_asks(line, spec):
    from ashugh.scan import scan
    from ashugh.spec import from_dict

    rep = scan(line + "\n", from_dict({"language": "en", **spec}))
    assert [i.message for i in rep.issues if i.code == "meter"] == []  # clósing-time, lóng-lost
