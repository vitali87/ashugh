"""Lines and tags as songwriters write them."""

import pytest

from ashugh import lyrics, suno
from ashugh.lang import en
from ashugh.scan import scan
from ashugh.spec import from_dict


def test_a_line_of_digits_is_kept_and_flagged():
    rep = scan("1, 2, 3, 4!\n", from_dict({"syllables": 4, "language": "en"}))
    assert len(rep.lines) == 1
    codes = {(i.code, i.severity) for i in rep.issues}
    assert ("script", "warning") in codes and ("syllables", "error") in codes


def test_a_line_of_digits_keeps_its_place_in_the_scheme():
    text = "I walk the day\n1, 2, 3\nI walk the way\nall through the night\n"
    rep = scan(text, from_dict({"rhyme": "ABAB", "language": "en"}))
    assert [lr.line.index for lr in rep.lines] == [0, 1, 2, 3]
    assert not any(i.code == "rhyme" and i.line == 3 for i in rep.issues)  # way / day still A


def test_backing_vocals_and_punctuation_alone_are_still_not_lines():
    assert lyrics.parse("(ooh, ooh)\n...\n—\nreal words\n")[0].text == "real words"


@pytest.mark.parametrize(
    "word,count", [("goin'", 2), ("lovin'", 2), ("rockin’", 2), ("nothin'", 2)]
)
def test_a_dropped_g_keeps_its_syllables(word, count):
    (token,) = lyrics.tokenize(f"we were {word}")[2:]
    assert token == word
    assert en.analyze_word(token).size == count


def test_an_apostrophe_inside_or_around_other_words_is_unchanged():
    assert lyrics.tokenize("don't 'cause rock'n'roll the boys' song") == [
        "don't",
        "cause",
        "rock'n'roll",
        "the",
        "boys",
        "song",
    ]


@pytest.mark.parametrize(
    "tag,key",
    [
        ("2nd Verse", "verse"),
        ("Verse 1 (Female)", "verse"),
        ("Final Chorus", "chorus"),
        ("Last Chorus", "chorus"),
        ("Chorus (x2)", "chorus"),
        ("Pre-Chorus", "pre-chorus"),
        ("Verse 2", "verse"),
        ("Припев х2", "chorus"),
        ("Bridge: soft", "bridge"),
    ],
)
def test_section_keys_ignore_ordinals_and_asides(tag, key):
    assert lyrics.section_key(tag) == key


def test_suno_writes_the_repeat_count_with_a_latin_x():
    out = suno.format_song("[Припев х2]\nДа да да\n", tags=True).text
    assert out.startswith("[Chorus x2]")
