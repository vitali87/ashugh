"""Round 15 of dogfooding, Armenian: what a songwriter found wrong."""

import pytest

from ashugh import meter, rhyme
from ashugh.scan import analyze_lines
from ashugh.spec import Spec


def words(line: str, lang: str = "hy"):
    (ln,) = analyze_lines(line, Spec(language=lang))
    return ln.words


def es_is_pronoun(line: str, nth: int = 0) -> bool:
    es = [w for w in words(line) if w.norm == "ես"][nth]
    return not es.clitic


def hy_rhyme(a: str, b: str) -> float:
    lines = analyze_lines(f"{a}\n{b}", Spec(language="hy"))
    return rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))[0]


@pytest.mark.parametrize(
    "line",
    [
        "Ոչ ես, ոչ դու",
        "եթե ոչ ես",
        "Նույնիսկ ես",
        "Նաև ես",
        "Հենց ես",
        "Կամ ես, կամ դու",
        "Միայն ես",
    ],
)
def test_es_after_a_negation_or_focus_word_is_the_pronoun(line):
    assert es_is_pronoun(line)


@pytest.mark.parametrize("line", ["Ինչու ես լռում", "Դու իմ սերն ես"])
def test_es_after_its_word_stays_the_auxiliary(line):
    assert not es_is_pronoun(line)


def test_och_es_rhymes_on_es():
    assert hy_rhyme("Մնացինք դու ու ես", "Չմնաց ոչ ես") >= 0.9
