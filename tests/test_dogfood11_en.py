"""Round 11 of dogfooding, English."""

import pytest

from ashugh.lang import analyze, en
from ashugh.lyrics import tokenize
from ashugh.scan import scan
from ashugh.spec import from_dict


def words(line: str):
    return analyze("en", tokenize(line), {}, line)


def errors(text: str, **spec):
    rep = scan(text, from_dict({"language": "en", **spec}))
    return [(i.code, i.message) for i in rep.issues if i.severity == "error"]


@pytest.mark.parametrize(
    "line",
    [
        "And all I want is you",
        "I know that it was you",
        "The only one is me",
        "My only love is him",
    ],
)
def test_a_pronoun_after_a_copula_takes_the_beat(line):
    assert errors(line + "\n", meter="iamb", feet=3, endings="m") == []


@pytest.mark.parametrize(
    "text,spec",
    [
        ("We sat beside the fire\n", {"endings": "m"}),
        ("Our love will last for every hour\n", {"meter": "iamb", "feet": 4, "endings": "m"}),
        ("She wrote her love a poem\nAnd sent it to his home\n", {"rhyme": "AA"}),
    ],
)
def test_a_word_sung_short_ends_and_rhymes_short(text, spec):
    assert errors(text, **spec) == []


def test_twenty_one_rhymes_with_sun():
    assert errors("When I was only twenty-one\nI lay beneath the sun\n", rhyme="AA") == []


def test_spring_is_one_syllable():
    assert en.analyze_word("spring").size == 1
    assert en.analyze_word("springs").size == 1


def test_a_name_variant_does_not_take_the_rhyme():
    text = "You shine brighter than the sun\nOur story only just begun\n"
    assert not [e for e in errors(text, meter="dolnik", feet=3, rhyme="AA") if e[0] == "rhyme"]
    assert [r.stress for r in en.analyze_word("eleven").readings] == [1]


def rhyme_score(a: str, b: str) -> float:
    from ashugh import meter, rhyme
    from ashugh.scan import analyze_lines
    from ashugh.spec import Spec

    lines = analyze_lines(f"{a}\n{b}", Spec(language="en"), "en")
    return rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))[0]


@pytest.mark.parametrize("a,b", [("care", "bell"), ("there", "well"), ("far", "fall")])
def test_r_and_l_are_no_near_rhyme(a, b):
    assert rhyme_score(a, b) < 0.7


@pytest.mark.parametrize(
    "token,stress", [("twenty-four-seven", 3), ("ice-cold", 1), ("Netflix-and-chill", 3)]
)
def test_a_hyphenated_compound_stresses_its_last_part(token, stress):
    assert en.analyze_word(token).readings[0].stress == stress


@pytest.mark.parametrize(
    "word,syllables", [("yeet", 1), ("highkey", 2), ("lowkey", 2), ("rizz", 1), ("bae", 1)]
)
def test_slang(word, syllables):
    w = en.analyze_word(word)
    assert w.size == syllables and not w.guessed


def test_bae_rhymes_with_day():
    assert errors("You are my bae\nI think of you all day\n", rhyme="AA") == []


def test_vibin_is_built_from_vibe():
    w = en.analyze_word("vibin'")
    assert w.readings[0].phones[:3] == ("v", "aɪ", "b") and not w.guessed


def test_email_is_stressed_on_e():
    assert en.analyze_word("emails").readings[0].stress == 0


@pytest.mark.parametrize("token,syllables", [("MC", 2), ("DJ", 2), ("FOMO", 2), ("YOLO", 2)])
def test_abbreviations_and_acronyms(token, syllables):
    assert en.analyze_word(token).size == syllables


def test_dr_is_doctor():
    assert en.analyze_word("Dr.").size == 2


def test_ol_apostrophe_is_known():
    assert not en.analyze_word("ol'").guessed


def test_no_misleading_short_note_without_a_spec():
    rep = scan("I know this love is real\n", from_dict({"language": "en"}))
    assert not any("one syllable fewer" in i.message for i in rep.issues)


def test_russian_r_and_l_still_rhyme():
    from ashugh.scan import scan as scan_

    rep = scan_(
        "Большой и шумный город\nИ зимний лютый холод\n",
        from_dict({"language": "ru", "rhyme": "AA"}),
    )
    assert not [i for i in rep.issues if i.code == "rhyme"]
