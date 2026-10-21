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
