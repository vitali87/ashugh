"""English spelling splits for held notes: compounds, gh, Mc-, h, syncope."""

import pytest

from ashugh.lang import en


@pytest.mark.parametrize(
    "word,pieces",
    [
        ("Broadway", ["Broad", "way"]),
        ("Lamborghini", ["Lam", "bor", "ghi", "ni"]),
        ("McDonald's", ["Mc", "Don", "ald's"]),
        ("Tahoe", ["Ta", "hoe"]),
        ("hundreds", ["hun", "dreds"]),
        ("children", ["chil", "dren"]),
        ("chocolate", ["choco", "late"]),
    ],
)
def test_held_note_splits(word, pieces):
    assert [s.text for s in en.analyze_word(word).syllables] == pieces


@pytest.mark.parametrize(
    "word,pieces",
    [
        ("laughing", ["laugh", "ing"]),
        ("every", ["ev", "e", "ry"]),
        ("lovely", ["love", "ly"]),
        ("fishing", ["fish", "ing"]),
        ("rock'n'roll", ["rock", "'n", "roll"]),
    ],
)
def test_splits_that_stay(word, pieces):
    assert [s.text for s in en.analyze_word(word).syllables] == pieces
