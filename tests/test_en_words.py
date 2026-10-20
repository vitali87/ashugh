"""English words a songwriter writes that the dictionary reads wrong or not at all."""

import pytest

from ashugh import lyrics
from ashugh.lang import en
from ashugh.scan import scan
from ashugh.spec import from_dict


@pytest.mark.parametrize("word", ["blessèd", "wingèd", "lovèd", "cursèd"])
def test_a_grave_on_ed_sings_it(word):
    w = en.analyze_word(word)
    assert w.size == 2 and w.readings[0].stress == 0  # bless-èd


def test_a_lexicon_entry_written_with_its_grave_is_used():
    w = en.analyze_word("wingèd", {"wingèd": "W IH0 NG IH1 D"})
    assert w.size == 2 and w.readings[0].stress == 1  # the entry's, not the dictionary's


@pytest.mark.parametrize("word", ["goest", "doest", "seest", "goeth", "doeth", "flyeth"])
def test_archaic_endings_after_a_vowel_are_a_syllable(word):
    w = en.analyze_word(word)
    assert w.size == 2 and w.readings[0].stress == 0  # go-est, fly-eth


def test_letters_glued_to_digits_are_no_word():
    assert lyrics.tokenize("back in the '80s, 4ever") == ["back", "in", "the"]


def test_an_ampersand_is_sung_as_and():
    rep = scan("Rock & roll\n", from_dict({"language": "en", "syllables": 3}))
    assert rep.ok and [w.norm for w in rep.lines[0].line.words] == ["rock", "and", "roll"]


def test_a_compound_with_a_short_second_word_after_a_silent_e():
    w = en.analyze_word("glovebox")
    assert w.size == 2 and not w.guessed  # glove-box, not glo-ve-box


@pytest.mark.parametrize("word,want", [("instagram", 0), ("polyglot", 0)])
def test_with_no_primary_stress_the_first_secondary_leads(word, want):
    r = en.analyze_word(word).readings[0]
    assert r.stress == want and r.secondary  # ín-sta-gràm


@pytest.mark.parametrize("a,b", [("yeah", "there"), ("yeah", "care")])
def test_yeah_rhymes_as_songs_sing_it(a, b):
    rep = scan(f"oh {a}\nI'm {b}\n", from_dict({"language": "en", "rhyme": "AA"}))
    assert [i for i in rep.issues if i.code == "rhyme"] == []


@pytest.mark.parametrize("word,sizes", [("real", {1, 2}), ("poem", {1, 2})])
def test_words_sung_either_length(word, sizes):
    w = en.analyze_word(word)
    assert {w.size, w.size - 1} == sizes and w.drop is not None


def test_real_is_one_syllable_unless_the_count_asks_two():
    assert scan("for real\n", from_dict({"language": "en", "syllables": 2})).ok
    assert scan("for real\n", from_dict({"language": "en", "syllables": 3})).ok
    assert scan("for real\n", from_dict({"language": "en"})).lines[0].fit.count == 2


@pytest.mark.parametrize(
    "word,want",
    [
        ("fishing", "fish-ing"),
        ("whiskey", "whis-key"),
        ("gathered", "gath-ered"),
        ("seven", "sev-en"),
        ("rocket", "rock-et"),
        ("fixin'", "fix-in'"),
        ("playin'", "play-in'"),
        ("paper", "pa-per"),
        ("little", "lit-tle"),
        ("beautiful", "beau-ti-ful"),
    ],
)
def test_held_note_pieces_keep_the_sound(word, want):
    assert en.analyze_word(word).sung() == want


def test_syl_warns_that_digits_are_not_counted(capsys):
    from ashugh.cli import main

    main(["syl", "I got your text at 2 a.m."])
    assert "digits" in capsys.readouterr().err


def test_an_accented_vowel_is_a_vowel_to_the_pieces():
    assert en.analyze_word("blessèd").sung() == "bles-sèd"  # a doubled consonant splits: lit-tle
    assert en.analyze_word("café").sung() == "ca-fé"


@pytest.mark.parametrize(
    "line", ["'Cause it's Tennessee whiskey and a Friday night", "A Japanese garden in the rain"]
)
def test_a_late_stress_moves_back_before_a_stressed_word(line):
    rep = scan(line + "\n", from_dict({"language": "en", "meter": "dolnik"}))
    assert [i.message for i in rep.issues if i.code == "meter"] == []  # TÉN-nes-see WHÍS-key


def test_a_late_stress_stays_where_nothing_clashes():
    rep = scan("I hope that you will understand\n", from_dict({"language": "en", "meter": "iamb4"}))
    assert rep.ok and rep.lines[0].fit.stresses[5] == 2  # un-der-stánd
