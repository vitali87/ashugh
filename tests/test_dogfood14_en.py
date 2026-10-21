"""Round 14 of dogfooding, English: what a songwriter found wrong."""

import pytest

from ashugh import meter, rhyme
from ashugh.scan import analyze_lines, scan
from ashugh.spec import Spec, from_dict


def rhymes(a: str, b: str) -> float:
    lines = analyze_lines(f"{a}\n{b}", Spec(language="en"))
    return rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))[0]


@pytest.mark.parametrize(
    "a, b",
    [
        ("holy fire", "sky"),
        ("desire", "high"),
        ("higher", "sky"),
        ("hour", "now"),
        ("power", "cow"),
    ],
)
def test_a_word_sung_short_keeps_its_r(a, b):
    assert rhymes(a, b) < rhyme.THRESHOLD["near"]


@pytest.mark.parametrize("a, b", [("tired", "tide"), ("every", "heavy")])
def test_an_r_more_or_less_is_no_perfect_rhyme(a, b):
    assert rhymes(a, b) < rhyme.THRESHOLD["perfect"]


@pytest.mark.parametrize(
    "a, b", [("fire", "retire"), ("fire", "higher"), ("hour", "sour"), ("tired", "admired")]
)
def test_r_words_still_rhyme_with_each_other(a, b):
    assert rhymes(a, b) >= rhyme.THRESHOLD["near"]


def test_fire_and_sky_fail_a_rhyme_scheme():
    rep = scan(
        "I saw the light of holy fire\nAnd watched it rising to the sky\n",
        from_dict({"language": "en", "rhyme": "AA", "meter": "iamb4"}),
    )
    assert not rep.ok


FIRE = (
    "[V]\nI saw the glory of the fire\nAnd all my heart was free\n"
    "I heard the music of the choir\nIt sang of you and me\n"
)


def test_a_song_passes_the_spec_derived_from_it():
    from ashugh.spec import dumps, loads
    from ashugh.translate import derive_spec

    src = scan(FIRE, from_dict({"language": "en"}))
    data = derive_spec(src, {"syllables", "meter", "rhyme", "endings"})
    rep = scan(FIRE, loads(dumps({"language": "en", **data})))
    assert not [i.message for i in rep.issues if i.severity == "error"]


def en_word(token: str):
    from ashugh.lang import en

    return en.analyze_word(token)


@pytest.mark.parametrize(
    "token, size", [("mornin's", 2), ("warnin's", 2), ("evenin's", 2), ("somethin's", 2)]
)
def test_a_dropped_g_plural_is_the_ing_plural(token, size):
    w = en_word(token)
    assert w.size == size and not w.guessed


def test_dropped_g_plurals_rhyme():
    assert rhymes("Holdin' on to Sunday mornin's", "Y'all can keep your city warnin's") >= 0.7


def test_evenins_is_stressed_on_its_first_syllable():
    assert en_word("evenin's").readings[0].stress == 0


@pytest.mark.parametrize(
    "token, size",
    [
        ("pow'r", 1),
        ("flow'r", 1),
        ("heav'n", 1),
        ("pray'r", 1),
        ("ev'ry", 2),
        ("wand'ring", 2),
        ("pow'rful", 2),
        ("fall'n", 1),
        ("hist'ry", 2),
        ("fam'ly", 2),
    ],
)
def test_a_vowel_elided_with_an_apostrophe_is_known(token, size):
    w = en_word(token)
    assert w.size == size and not w.guessed


@pytest.mark.parametrize("a, b", [("pow'r", "hour"), ("heav'n", "leav'n"), ("o'er", "more")])
def test_elided_words_rhyme_as_they_sound(a, b):
    assert rhymes(a, b) >= rhyme.THRESHOLD["near"]


@pytest.mark.parametrize("token", ["don't", "we'll", "y'all", "ma'am", "o'clock"])
def test_contractions_are_read_as_the_dictionary_lists_them(token):
    from ashugh.lang import en

    listed = en.TABLE.get(token)
    assert listed is not None and en.lookup(token) == listed.split("|")
