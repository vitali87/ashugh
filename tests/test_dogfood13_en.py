"""Round 13 of dogfooding, English: what a songwriter found wrong."""

import pytest

from ashugh import suno
from ashugh.lang import en
from ashugh.scan import analyze_lines
from ashugh.spec import Spec, from_dict


def words(text: str) -> list:
    (ln,) = analyze_lines(text, Spec(language="en"))
    return ln.words


@pytest.mark.parametrize("token, sung", [("FYI", "F-Y-I"), ("AKA", "A-K-A")])
def test_an_abbreviation_the_dictionary_spells_or_expands_is_sung_letter_by_letter(token, sung):
    (w,) = words(f"{token}\n")
    assert w.spelled and w.size == 3 and w.sung().replace("(", "").startswith(sung[:1])
    assert "-".join(s.text for s in w.syllables) == sung


def test_a_lowercase_abbreviation_with_more_syllables_than_letters_is_not_garbled():
    (w,) = words("etc\n")
    assert w.size == 4 and "-".join(s.text for s in w.syllables) != "e-t-c-e"


def split(line: str) -> str:
    return suno.format_song(line + "\n", tags=False, split="all").text.strip()


def test_suno_writes_a_spelled_abbreviation_as_its_letters():
    assert split("WTF") == "W-T-F"
    assert split("I got a W tonight") == "I got a W to-night"


def test_w_with_a_slash_is_with():
    (_, w, _) = words("me w/ you\n")
    assert w.size == 1


@pytest.mark.parametrize(
    "word, pieces",
    [
        ("science", "sci-ence"),
        ("violence", "vi-o-lence"),
        ("audience", "aud-i-ence"),
        ("seeing", "see-ing"),
        ("doing", "do-ing"),
        ("playing", "play-ing"),
        ("magician", "ma-gi-cian"),
        ("musician", "mu-si-cian"),
        ("orange", "or-ange"),
        ("forest", "for-est"),
        ("story", "sto-ry"),
        ("nation", "na-tion"),
        ("passion", "pas-sion"),
    ],
)
def test_written_words_are_cut_where_they_are_sung(word, pieces):
    assert "-".join(s.text for s in en.analyze_word(word).syllables) == pieces


@pytest.mark.parametrize(
    "line, out",
    [
        ("Come on baby light my fire", "fi-er"),
        ("We will dance until the hour", "hou-er"),
        ("I feel the power of desire", "de-si-er"),
    ],
)
def test_suno_writes_a_long_sung_ire_or_our_as_it_sounds(line, out):
    spec = from_dict({"language": "en", "syllables": len(line.split()) + 2})
    got = suno.format_song(line + "\n", spec=spec, tags=False, split="last").text
    assert got.split()[-1] == out


def test_suno_marks_a_dropped_vowel_with_an_apostrophe():
    spec = from_dict({"language": "en", "syllables": 4})
    got = suno.format_song("every day I wait\n", spec=spec, tags=False, split="all").text
    assert got.split()[0] == "ev'-ry"


GROUP = (
    "[Verse 1]\nMy daddy ran the feed store down\nBeside the old county line\n"
    "He hollered y'all come back around\nWe close up shop at ten\n"
)


def test_a_partner_rhymes_with_a_line_that_has_no_fix_as_it_is_written():
    from ashugh.fit import fit_song
    from ashugh.proposers import StaticProposer

    spec = from_dict({"language": "en", "syllables": [8, 6], "meter": "iamb", "rhyme": "ABAB"})
    res = fit_song(GROUP, spec, StaticProposer({5: ["We close up shop at nine"]}), rounds=1)
    assert [c.line for c in res.changes] == [5]
    assert res.text.splitlines()[4] == "We close up shop at nine"
    assert [u.line for u in res.unresolved] == [3]
