"""Round 13 of dogfooding, Armenian: what a songwriter found wrong."""

import pytest

from ashugh import suno
from ashugh.lang import hy
from ashugh.scan import analyze_lines
from ashugh.spec import Spec


def words(line: str):
    (ln,) = analyze_lines(line, Spec(language="hy"))
    return ln.words


def shown(w) -> str:
    return "-".join(s.text for s in w.syllables)


@pytest.mark.parametrize(
    "token, pieces",
    [
        ("ԱՄՆ-ից", "Ա-Մե-Նե-ից"),
        ("ԵՊՀ-ից", "Ե-Պե-Հա-յից"),
        ("ՀՀ-ի", "Հա-Հա-յի"),
        ("ՀՀԿ-ն", "Հա-Հա-Կան"),
        ("ԱՄՆ-ում", "Ա-Մե-Նե-ում"),
    ],
)
def test_an_abbreviation_with_a_case_ending_is_spelt_and_takes_it(token, pieces):
    (w,) = words(token)
    assert w.spelled and shown(w) == pieces
    assert w.readings[0].stress == w.size - 1  # the ending, as Armenian stresses the end


@pytest.mark.parametrize("token", ["Երևան-Գյումրի", "ՆԱՏՕ-ի", "ԱՄՆ-Ռուսաստան"])
def test_other_hyphenated_words_are_no_spelt_abbreviation(token):
    assert not words(token)[0].spelled


def test_suno_writes_the_ending_after_the_letters():
    out = suno.format_song("ԱՄՆ-ից, ՀՀ-ի\n", tags=False, armenian="latin").text
    assert "A-Me-Ne-its" in out and "Ha-Ha-yi" in out


def test_a_vowelless_abbreviation_is_spelt_in_a_line_in_capitals():
    w = words("ՀՀ ՀԱՅԱՍՏԱՆ")
    assert w[0].spelled and w[0].size == 2 and not w[1].spelled


def test_a_syllable_count_counts_the_letters():
    assert sum(w.size for w in words("Ես եկա ԱՄՆ-ից քեզ մոտ")) == 9


def test_analyze_word_alone():
    assert hy.analyze_word("ՀՀ-ի").size == 3
