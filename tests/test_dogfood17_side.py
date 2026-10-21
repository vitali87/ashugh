"""Judgment calls from round 16, settled: rhymes English singers hear as one."""

import pytest

from ashugh import meter, rhyme
from ashugh.scan import analyze_lines
from ashugh.spec import Spec


def en_rhyme(a: str, b: str) -> float:
    lines = analyze_lines(f"{a}\n{b}", Spec(language="en"))
    return rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))[0]


@pytest.mark.parametrize(
    "a,b",
    [
        ("falling", "calling"), ("fall", "call"), ("rock", "talk"), ("cot", "caught"),
        ("beautiful", "dutiful"), ("merrily", "verily"), ("faces", "places"),
    ],
)  # fmt: skip
def test_rhymes_english_singers_hear_as_one(a, b):
    assert en_rhyme(a, b) >= rhyme.THRESHOLD["perfect"]


@pytest.mark.parametrize("a,b", [("far", "war"), ("still", "feel"), ("sitting", "meeting")])
def test_contrasts_english_keeps(a, b):
    assert en_rhyme(a, b) < rhyme.THRESHOLD["near"]


def test_a_last_unstressed_vowel_still_counts():
    assert en_rhyme("happy", "grappa") < rhyme.THRESHOLD["perfect"]


SPOKEN = (
    "[Verse 1]\nI walked along the empty street\n\n"
    "[Spoken Word]\nAnd then she said, I'll never come back here again\n"
)


def test_a_spoken_section_is_not_held_to_the_songs_line():
    from ashugh.scan import scan
    from ashugh.spec import from_dict

    report = scan(SPOKEN, from_dict({"language": "en", "syllables": 8, "meter": "iamb"}))
    assert all(lr.ok for lr in report.lines)


def test_a_spoken_section_keeps_its_own_table():
    from ashugh.scan import scan
    from ashugh.spec import from_dict

    spec = {"language": "en", "syllables": 8, "section": {"spoken word": {"syllables": 10}}}
    report = scan(SPOKEN, from_dict(spec))
    assert not report.lines[1].ok


def test_a_sung_section_still_is():
    from ashugh.scan import scan
    from ashugh.spec import from_dict

    text = SPOKEN.replace("[Spoken Word]", "[Bridge]")
    report = scan(text, from_dict({"language": "en", "syllables": 8}))
    assert not report.lines[1].ok
