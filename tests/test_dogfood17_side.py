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
