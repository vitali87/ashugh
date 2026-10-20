"""ես: the pronoun I [jes], or the auxiliary (you are) [es] that leans on the word before."""

import pytest

from ashugh import lyrics, meter, rhyme, suno
from ashugh.lang import analyze
from ashugh.scan import analyze_lines
from ashugh.spec import Spec


def score(a: str, b: str) -> float:
    lines = analyze_lines(f"{a}\n{b}", Spec(language="hy"), "hy")
    return rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))[0]


def es_word(line: str, k: int = -1):
    words = analyze("hy", lyrics.tokenize(line), {}, line)
    found = [w for w in words if w.norm == "ես"]
    return found[k]


@pytest.mark.parametrize(
    "line", ["Դու գալիս ես", "Դու գեղեցիկ ես", "Ինչու ես լռում", "Դու իմ սերն ես", "Որտեղ ես, սեր"]
)
def test_the_auxiliary_leans_and_has_no_y(line):
    w = es_word(line, 0)
    assert w.enclitic and w.readings[0].phones[0] != "j"


@pytest.mark.parametrize(
    "line,k",
    [("Ես գնում եմ", 0), ("Հիմա ես գիտեմ", 0), ("Ես եմ, ես եմ", 1), ("Ու ես կգամ", 0)],
)
def test_the_pronoun_opens_its_clause_or_has_its_own_verb(line, k):
    w = es_word(line, k)
    assert not w.enclitic and w.readings[0].phones[0] == "j"


def test_the_auxiliary_rhymes_like_its_neighbours():
    a = score("գալիս ես", "լալիս եք")
    b = score("գալիս եմ", "լալիս եք")
    assert a == pytest.approx(b)  # [lisɛs] / [lisɛkʰ], as [lisɛm] / [lisɛkʰ]; not [lisjɛs]


@pytest.mark.parametrize(
    "line,want",
    [
        ("Հիմա ես գիտեմ", "Hima yes gitem"),
        ("Ես եմ, ես եմ", "Yes em, yes em"),
        ("Դու գեղեցիկ ես", "Du geghetsik es"),
    ],
)
def test_latin_letters_follow_the_same_reading(line, want):
    assert suno.format_song(line, armenian="latin", tags=False).text == want
