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
