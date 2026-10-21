"""Contemporary English lyrics, from the tenth dogfooding round."""

import pytest

from ashugh.cli import main
from ashugh.lang import en
from ashugh.scan import scan
from ashugh.spec import from_dict


def errors(text: str, **spec) -> list[str]:
    rep = scan(text, from_dict({"language": "en", **spec}))
    return [f"L{i.line} {i.message}" for i in rep.issues if i.severity == "error"]


@pytest.mark.parametrize(
    "text, meter",
    [
        ("And every night I'm missing you\nThe way that you keep calling me\n", "iamb4"),
        ("Baby, you just ghosted me\nThen you went and posted it\n", "trochee4"),
        ("And now I'm sittin' here, just missin' you\n", "iamb5"),
    ],
)
def test_a_final_pronoun_after_a_verb_takes_the_last_foot(text, meter):
    assert errors(text, meter=meter) == []


def level(a: str, b: str, capsys) -> str:
    main(["rhyme", a, b])
    return capsys.readouterr().out.split()[0]


@pytest.mark.parametrize(
    "a, b", [("real", "feel"), ("real", "deal"), ("goin'", "blowin'"), ("cryin'", "tryin'"),
             ("drinkin'", "thinkin'")],
)  # fmt: skip
def test_a_sung_short_form_rhymes_as_sung(a, b, capsys):
    assert level(a, b, capsys) == "perfect"


def test_real_rhymes_with_feel_in_a_line():
    text = "You know I gotta keep it real\nYou know I like the way I feel\n"
    assert errors(text, meter="iamb4", rhyme="AA") == []


def test_ya_is_an_object_pronoun():
    text = "I swear I'm gonna find ya\nI'm always right behind ya\n"
    assert errors(text, meter="iamb3", rhyme="AA") == []
    found = errors("Oh baby, how I want ya\nOh baby, how I need ya\n", rhyme="AA")
    assert "L2 rhyme A broken" in found  # the same pronoun twice is no rhyme


@pytest.mark.parametrize(
    "word, size", [("LA", 2), ("AM", 2), ("NYC", 3), ("BFF", 3), ("DMs", 2), ("OMG", 3),
                   ("DIY", 3), ("ATL", 3), ("la", 1), ("LOVE", 1)],
)  # fmt: skip
def test_a_capitalised_abbreviation_is_spelled_out(word, size):
    assert en.analyze_word(word).size == size


def test_la_rhymes_with_away():
    text = "You said you'd never leave LA\nAnd I just watched you drive away\n"
    assert errors(text, meter="iamb4", rhyme="AA") == []


def test_ba_is_a_vocable_not_a_degree():
    assert en.analyze_word("ba").size == 1


@pytest.mark.parametrize(
    "word, size, stress",
    [("ghosted", 2, 0), ("ghosting", 2, 0), ("vibing", 2, 0), ("influencer", 4, 0),
     ("woah", 1, 0)],
)  # fmt: skip
def test_an_unlisted_inflection_is_its_stem_and_an_ending(word, size, stress):
    w = en.analyze_word(word)
    assert (w.size, w.readings[0].stress, w.guessed) == (size, stress, False)


def test_ghosted_rhymes_with_posted():
    text = "You liked my selfie, then you ghosted\nI saw the pictures that you posted\n"
    assert errors(text, meter="iamb4", rhyme="AA") == []


def test_an_unknown_monosyllable_is_warned_about():
    rep = scan("I need my zorb tonight\n", from_dict({"language": "en"}))
    assert any("zorb" in i.message for i in rep.issues if i.severity == "warning")


def test_split_keeps_the_apostrophe_of_have():
    from ashugh import suno

    out = suno.format_song("I would've called you\n", split="all", tags=False).text
    assert "would-'ve" in out or "would've" in out


def test_a_known_monosyllable_is_not_warned_about():
    rep = scan("I need my love tonight\n", from_dict({"language": "en"}))
    assert not any("unknown" in i.message for i in rep.issues)


def test_an_unknown_monosyllable_is_named_once_per_line():
    rep = scan("zorb zorb zorb tonight\n", from_dict({"language": "en"}))
    assert sum("zorb" in i.message for i in rep.issues) == 1


def test_split_keeps_the_consonant_before_an_apostrophe():
    from ashugh.lang import en

    assert [s.text for s in en.analyze_word("rock'n'roll").syllables][0] == "rock"
    assert [s.text for s in en.analyze_word("somethin'").syllables] == ["some", "thin'"]
    assert [s.text for s in en.analyze_word("fishing").syllables] == ["fish", "ing"]
