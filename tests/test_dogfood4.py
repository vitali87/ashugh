"""Round four of dogfooding: what fresh lyrics found wrong."""

import pytest

from ashugh.lang import en
from ashugh.scan import scan
from ashugh.spec import from_dict


def errors(rep):
    return [(i.line, i.code, i.message) for i in rep.issues if i.severity == "error"]


@pytest.mark.parametrize(
    "word", ["desire", "entire", "empire", "power", "flower", "tower", "higher", "tire"]
)
def test_ire_and_our_may_merge_into_one_syllable_like_fire(word):
    w = en.analyze_word(word)
    assert w.drop == w.size - 1 and w.drop_cost == 0  # de-sire or de-si-re, pow'r or po-wer


@pytest.mark.parametrize("word", ["tiger", "spider", "louder", "lion", "loyal"])
def test_a_consonant_or_another_vowel_between_keeps_both_syllables(word):
    assert en.analyze_word(word).drop is None


@pytest.mark.parametrize("count", [4, 5])
def test_a_line_counts_power_either_way(count):
    rep = scan("I feel the power", from_dict({"language": "en", "syllables": count}))
    assert errors(rep) == []


@pytest.mark.parametrize("word", ["empire", "sapphire", "vampire", "birdhouse"])
def test_an_unreduced_diphthong_after_the_stress_is_a_secondary_stress(word):
    (main, *_) = en.analyze_word(word).readings
    assert main.stress == 0 and 1 in main.secondary


@pytest.mark.parametrize("word", ["lion", "tiger", "highest"])
def test_a_reduced_vowel_after_the_stress_is_not(word):
    assert all(r.secondary == () for r in en.analyze_word(word).readings)


@pytest.mark.parametrize("partner", ["fire", "desire", "higher"])
def test_empire_rhymes_with_fire_on_its_second_syllable(partner):
    rep = scan(
        f"I built myself an empire\nAnd watched it burn in {partner}",
        from_dict({"language": "en", "rhyme": "AA"}),
    )
    assert errors(rep) == []


def test_empire_still_does_not_rhyme_with_a_word_on_its_first_syllable():
    rep = scan(
        "I built myself an empire\nAnd then I lost my temper",
        from_dict({"language": "en", "rhyme": "AA", "min_rhyme": "perfect"}),
    )
    assert errors(rep) == [(2, "rhyme", "rhyme A broken")]


@pytest.mark.parametrize("count", [7, 8, 9])
def test_held_note_pieces_add_up_to_the_count_for_ire_and_our(count):
    from ashugh import suno

    spec = from_dict({"language": "en", "syllables": count})
    out = suno.format_song("I feel the power of desire", spec=spec, split="all", tags=False).text
    assert sum(len(word.split("-")) for word in out.split()) == count
    if count == 9:
        assert out == "I feel the po-wer of de-si-re"
    if count == 7:
        assert out == "I feel the power of de-sire"
