"""Round 15 of dogfooding, English: what a songwriter found wrong."""

import pytest

from ashugh import meter, rhyme
from ashugh.scan import analyze_lines, scan
from ashugh.spec import Spec, from_dict


def words(line: str):
    (ln,) = analyze_lines(line, Spec(language="en"))
    return ln.words


def rhymes(a: str, b: str) -> float:
    lines = analyze_lines(f"{a}\n{b}", Spec(language="en"))
    return rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))[0]


@pytest.mark.parametrize(
    "text,spec",
    [
        ("Put on the record\nThe crowd adored\n", {"rhyme": "AA"}),
        ("Put on my record\nThe crowd adored\n", {"rhyme": "AA"}),
        ("We cross the desert\nForever alert\n", {"rhyme": "AA"}),
        ("I found a present\nThat I resent\n", {"rhyme": "AA"}),
    ],
)
def test_a_noun_after_a_determiner_cannot_buy_a_rhyme_with_the_verb_stress(text, spec):
    report = scan(text, from_dict({"language": "en", **spec}))
    assert any(i.code == "rhyme" and i.severity == "error" for i in report.issues)


@pytest.mark.parametrize("line", ["I want to record", "They will object", "we present"])
def test_a_verb_after_its_subject_keeps_the_verb_stress(line):
    assert words(line)[-1].readings[0].stress == 1


@pytest.mark.parametrize(
    "token,size",
    [
        ("whyyyy", 1), ("nooooo", 1), ("Babyyyy", 2), ("Yeahhhh", 1), ("Ooooh", 1), ("Aaah", 1),
        ("looove", 1), ("Yesss", 1), ("Loooong", 1), ("Heyyyy", 1), ("Mmmmm", 1), ("Sooooo", 1),
    ],
)  # fmt: skip
def test_an_elongated_word_is_its_word_held(token, size):
    w = words(token)[0]
    assert w.size == size and not w.guessed, [r.source for r in w.readings]
    assert "".join(s.text for s in w.syllables) == token


@pytest.mark.parametrize(
    "a,b", [("Tell me whyyyy", "sky"), ("Baby, nooooo", "so"), ("looove", "above")]
)
def test_an_elongated_word_rhymes_as_its_word(a, b):
    assert rhymes(a, b) >= 0.9


def test_a_sound_with_a_triple_letter_stays_itself():
    assert words("Brrr")[0].size == 1


@pytest.mark.parametrize(
    "text",
    [
        "We danced until the midnight\nUnder the silver light\n",
        "Sleep, little sparrow, goodnight\nStars on the water are bright\n",
    ],
)
def test_a_secondary_stress_rhyme_takes_its_ending_from_that_stress(text):
    from ashugh.translate import derive_spec

    data = derive_spec(scan(text), {"rhyme", "endings"})
    assert data["stanza"]["1"]["endings"] == "mm"
    report = scan(text, from_dict({"language": "en", "endings": "mm", "rhyme": "AA"}))
    assert report.ok, report.issues


def test_a_primary_ending_still_counts():
    report = scan("We danced until the midnight\n", from_dict({"language": "en", "endings": "f"}))
    assert report.ok, report.issues
