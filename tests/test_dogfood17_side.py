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


@pytest.mark.parametrize(
    "word,n",
    [
        ("Persephone", 4), ("Eurydice", 4), ("Niobe", 3), ("Circe", 2), ("Urania", 4),
        ("Terpsichore", 4), ("Persephone's", 4),
    ],
)  # fmt: skip
def test_greek_names_are_counted_in_full(word, n):
    (ln,) = analyze_lines(word, Spec(language="en"))
    (w,) = ln.words
    assert w.size == n and not w.assumed and not w.guessed


def test_a_possessive_after_a_vowel_adds_no_syllable():
    (ln,) = analyze_lines("Persephone's", Spec(language="en"))
    assert ln.words[0].sung() == "Per-seph-o-ne's"


def test_lyres_and_fires_are_counted_alike():
    from ashugh.scan import scan
    from ashugh.translate import derive_spec

    report = scan("Amid the lyres\nAround the fires\n")
    assert [lr.fit.count for lr in report.lines] == [4, 4]
    assert derive_spec(report, {"endings"})["stanza"]["1"]["endings"] == "mm"


def test_a_line_may_still_sing_fire_in_two():
    from ashugh.scan import scan
    from ashugh.spec import from_dict

    assert scan("Come on baby light my fire\n", from_dict({"syllables": 8})).lines[0].ok


@pytest.mark.parametrize(
    "word,stress",
    [
        ("pussy-cat", 0), ("sweet-heart", 0), ("heart-break", 0), ("mother-in-law", 0),
        ("merry-go-round", 0), ("twenty-one", 2), ("ice-cold", 1), ("well-known", 1),
        ("rock-and-roll", 2), ("good-bye", 1),
    ],
)  # fmt: skip
def test_a_hyphenated_compound_takes_the_stress_the_dictionary_gives_it_whole(word, stress):
    (ln,) = analyze_lines(word, Spec(language="en"))
    assert ln.words[0].readings[0].stress == stress


def test_the_owl_and_the_pussycat_scans():
    from ashugh.scan import scan

    report = scan("The owl and the pussy-cat went to sea\n")
    assert report.lines[0].fit.stresses[3] == 0  # PUS-sy-cat
