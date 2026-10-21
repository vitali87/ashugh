"""An Armenian song's lines in Latin letters that mix English and Armenian words."""

import pytest

from ashugh.scan import analyze_lines
from ashugh.spec import Spec


def words(line: str):
    (ln,) = analyze_lines(line, Spec(language="hy"))
    return ln.words


@pytest.mark.parametrize(
    "line, word, lang",
    [
        ("sirum em qez baby", "baby", "en"),  # an English word in an Armenian line
        ("baby, sirum em qez", "baby", "en"),
        ("sirum em qez baby", "sirum", "hy"),
        ("oh baby kyanqs", "kyanqs", "hy"),  # an Armenian word in an English line
        ("I love you, sirum em qez", "sirum", "hy"),
        ("I love you, sirum em qez", "em", "hy"),  # the auxiliary after it
        ("I love you, sirum em qez", "love", "en"),
        ("lav a, qez sirum em", "a", "hy"),  # ա, not the English article
    ],
)
def test_each_word_is_read_in_its_own_language(line, word, lang):
    w = next(w for w in words(line) if w.text.strip(",") == word)
    assert w.lang == lang


def test_an_armenian_possessive_in_an_english_line_counts_its_schwa():
    assert sum(w.size for w in words("oh baby kyanqs")) == 5  # kyan-kʰəs


def test_an_english_line_of_an_armenian_song_stays_english():
    assert all(w.lang == "en" for w in words("I love you baby tonight"))


def test_outside_an_armenian_song_nothing_changes():
    (ln,) = analyze_lines("oh baby kyanqs", Spec(language="en"))
    assert all(w.lang == "en" for w in ln.words)
