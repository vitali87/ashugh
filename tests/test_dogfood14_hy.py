"""Round 14 of dogfooding, Armenian: what a songwriter found wrong."""

import pytest

from ashugh import suno
from ashugh.scan import analyze_lines
from ashugh.spec import Spec


def words(line: str):
    (ln,) = analyze_lines(line, Spec(language="hy"))
    return ln.words


@pytest.mark.parametrize(
    "line, k",
    [
        ("Ես ՔԵԶ եմ սիրում", 1),
        ("ՈՒՐ ես", 0),
        ("ԵՍ ու ԴՈՒ", 0),
        ("ԵՍ ու ԴՈՒ", 2),
        ("Դու ԻՄ սերն ես", 1),
        ("Ու ՆԱ եկավ", 1),
        ("ՄԵՐ երգը", 0),
        ("ՈՉ, ՉԷ", 0),
        ("ԻՆՁ տուր", 0),
    ],
)
def test_a_short_word_in_capitals_is_a_word(line, k):
    w = words(line)[k]
    assert not w.spelled and w.size == 1


@pytest.mark.parametrize(
    "token, size", [("ԱՄՆ", 3), ("ԵՊՀ", 3), ("ՀՀ", 2), ("ԱԺ", 2), ("ՀՀԿ-ն", 3)]
)
def test_abbreviations_are_still_spelt(token, size):
    (w,) = words(token)
    assert w.spelled and w.size == size


def test_suno_leaves_an_emphasized_word_as_written():
    out = suno.format_song("Ես ՔԵԶ եմ սիրում, ՈՒՐ ես, ԴՈՒ\n", tags=False).text
    assert out.startswith("Ես ՔԵԶ եմ սիրում, ՈՒՐ ես, ԴՈՒ")


def es_is_pronoun(line: str, nth: int = 0) -> bool:
    es = [w for w in words(line) if w.norm == "ես"][nth]
    return not es.clitic


@pytest.mark.parametrize(
    "line",
    [
        "Կերգեմ ես",
        "Սիրում եմ քեզ ես",
        "Չեմ մոռանա ես",
        "Մի օր ես կգայի",
        "Գիշերը ես չեկա",
        "Գիշերները ես քուն չեղա",
        "Քեզ համար միշտ կերգեմ ես,",
        "Հետո էլ ես գնացի",
    ],
)
def test_es_with_a_verb_of_i_in_its_clause_is_the_pronoun(line):
    assert es_is_pronoun(line)


@pytest.mark.parametrize(
    "line",
    [
        "Դու էլ ես գեղեցիկ",
        "Ե՞րբ ես գալու",
        "Ուր ես, ես կգամ",  # the first: the clause ends after it
        "Գիտեմ, որ դու ինձ սիրում ես",
        "Ինչու ես լռում",
        "Հայի պես ես խոսում",  # հայի is a genitive, no verb of I
    ],
)
def test_es_after_its_word_with_no_verb_of_i_is_the_auxiliary(line):
    assert not es_is_pronoun(line)


def test_suno_sings_the_pronoun_yes():
    out = suno.format_song("Կերգեմ ես\nԴու էլ ես գեղեցիկ\n", tags=False, armenian="latin").text
    assert "Kergem yes" in out and "Du el es" in out
