"""Round 14 of dogfooding, English: what a songwriter found wrong."""

import pytest

from ashugh import meter, rhyme
from ashugh.scan import analyze_lines, scan
from ashugh.spec import Spec, from_dict


def rhymes(a: str, b: str) -> float:
    lines = analyze_lines(f"{a}\n{b}", Spec(language="en"))
    return rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))[0]


@pytest.mark.parametrize(
    "a, b",
    [
        ("holy fire", "sky"),
        ("desire", "high"),
        ("higher", "sky"),
        ("hour", "now"),
        ("power", "cow"),
    ],
)
def test_a_word_sung_short_keeps_its_r(a, b):
    assert rhymes(a, b) < rhyme.THRESHOLD["near"]


@pytest.mark.parametrize("a, b", [("tired", "tide"), ("every", "heavy")])
def test_an_r_more_or_less_is_no_perfect_rhyme(a, b):
    assert rhymes(a, b) < rhyme.THRESHOLD["perfect"]


@pytest.mark.parametrize(
    "a, b", [("fire", "retire"), ("fire", "higher"), ("hour", "sour"), ("tired", "admired")]
)
def test_r_words_still_rhyme_with_each_other(a, b):
    assert rhymes(a, b) >= rhyme.THRESHOLD["near"]


def test_fire_and_sky_fail_a_rhyme_scheme():
    rep = scan(
        "I saw the light of holy fire\nAnd watched it rising to the sky\n",
        from_dict({"language": "en", "rhyme": "AA", "meter": "iamb4"}),
    )
    assert not rep.ok


FIRE = (
    "[V]\nI saw the glory of the fire\nAnd all my heart was free\n"
    "I heard the music of the choir\nIt sang of you and me\n"
)


def test_a_song_passes_the_spec_derived_from_it():
    from ashugh.spec import dumps, loads
    from ashugh.translate import derive_spec

    src = scan(FIRE, from_dict({"language": "en"}))
    data = derive_spec(src, {"syllables", "meter", "rhyme", "endings"})
    rep = scan(FIRE, loads(dumps({"language": "en", **data})))
    assert not [i.message for i in rep.issues if i.severity == "error"]
