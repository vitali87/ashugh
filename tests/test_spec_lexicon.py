"""[lexicon] entries are checked when the spec loads, not silently ignored."""

import pytest

from ashugh.spec import SpecError, from_dict


def load(word, value):
    return from_dict({"lexicon": {word: value}})


@pytest.mark.parametrize(
    "word,value",
    [
        ("замок", "замо́к"),
        ("замок", "замОк"),
        ("все", "всё"),
        ("Замок", "за́мок"),
        ("кот", "кот"),  # one vowel: nothing to mark
        ("zorblax", "Z AO1 R B L AE0 K S"),
        ("tomato", "T AH0 M EY1 T OW2"),
        ("կայսրություն", "կայ-սը-րու-թյուն"),
        ("սկսել", "ըս-կը-սել"),
        ("ու", "ու"),
        ("և", "և"),
    ],
)
def test_good_entries_load(word, value):
    assert load(word, value).lexicon[word.lower()] == value


@pytest.mark.parametrize(
    "word,value,message",
    [
        ("замок", "замок", "no stress"),
        ("замок", "заМок", "no stress"),
        ("замок", "заму́к", "different word"),
        ("zorblax", "zor-blax", "ARPABET"),
        ("zorblax", "Z AO R B L AE K S", "stress digit"),
        ("zorblax", "Z QQ1 R", "ARPABET"),
        ("կայսրություն", "կայսրություն", "hyphen"),
        ("կայսրություն", "կայսը-րու-թյուն", "one vowel"),
        ("կայսրություն", "կայ-սը-րու-թյան", "different word"),
        ("կայսրություն", "kay-sə-ru", "Armenian"),
    ],
)
def test_bad_entries_are_refused_with_the_word_and_the_way_to_write_it(word, value, message):
    with pytest.raises(SpecError, match=message) as e:
        load(word, value)
    assert word in str(e.value)


def test_words_in_other_scripts_are_left_alone():
    assert load("λόγος", "anything").lexicon["λόγος"] == "anything"


def test_a_stanza_table_overrides_its_sections_rules_not_the_top_levels():
    from ashugh.scan import scan

    spec = from_dict(
        {
            "language": "en",
            "meter": "iamb4",
            "rhyme": "AbAb",
            "section": {"chorus": {"meter": "trochee4", "rhyme": "AABB"}},
            "stanza": {"2": {"tolerance": 1}},
        }
    )
    text = "[Verse]\na\nb\nc\nd\n\n[Chorus]\ne\nf\ng\nh\n"
    rep = scan(text, spec)
    chorus = rep.units[1].rule
    assert (chorus.meter, chorus.rhyme, chorus.tolerance) == ("trochee", "AABB", 1)
    verse = rep.units[0].rule
    assert (verse.meter, verse.rhyme, verse.tolerance) == ("iamb", "AbAb", 0)
    assert spec.rule_for("chorus", 1) is spec.rule_for("chorus", 1)  # one rule per stanza
