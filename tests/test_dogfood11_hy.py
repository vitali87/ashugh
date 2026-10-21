"""Round 11 of dogfooding, Armenian."""

import pytest

from ashugh.lang import analyze, hy
from ashugh.lyrics import tokenize
from ashugh.scan import scan
from ashugh.spec import from_dict


def words(line: str):
    return analyze("hy", tokenize(line), {}, line)


def test_colloquial_a_is_the_auxiliary():
    ws = words("լավ ա")
    assert ws[1].enclitic and ws[1].clitic


def test_lines_ending_on_a_rhyme_on_the_word_before():
    rep = scan(
        "Մաման ասում ա՝ հերիք ա,\nԱսում ա, որ սիրում ա։\n",
        from_dict({"language": "hy", "rhyme": "AA"}),
    )
    assert not any("with itself" in i.message for i in rep.issues)
    assert any(i.code == "rhyme" for i in rep.issues), "հերիք ա / սիրում ա do not rhyme"


@pytest.mark.parametrize(
    "word,syllables",
    [("քաղաքս", 3), ("հայրենիքս", 4), ("ընտանիքս", 4), ("տանիքս", 3)],
)
def test_possessive_s_after_a_vowel_and_k_takes_a_schwa(word, syllables):
    assert hy.analyze_word(word).size == syllables


@pytest.mark.parametrize(
    "word,syllables", [("ինդեքս", 2), ("ռեմիքս", 2), ("միքս", 1), ("ֆաքս", 1), ("պարադոքս", 3)]
)
def test_a_loanword_in_ks_keeps_its_stem(word, syllables):
    assert hy.analyze_word(word).size == syllables


@pytest.mark.parametrize("a,b", [("երգ", "բերք"), ("մարդ", "զարթ")])
def test_a_voiced_stop_after_r_is_said_aspirated(a, b):
    pa, pb = hy.analyze_word(a), hy.analyze_word(b)
    assert pa.readings[0].phones[-1] == pb.readings[0].phones[-1]


def test_a_voiced_stop_elsewhere_stays_voiced():
    assert hy.analyze_word("բերդ").readings[0].phones[-1] == "tʰ"
    assert hy.analyze_word("հոգ").readings[0].phones[-1] == "g"


@pytest.mark.parametrize(
    "tag,name",
    [
        ("Կուպլետ 1", "Verse 1"),
        ("Ինտրո", "Intro"),
        ("Աութրո", "Outro"),
        ("Բրիջ", "Bridge"),
        ("Ռեֆրեն", "Chorus"),
        ("Նախերգանք", "Intro"),
        ("Նախակրկներգ", "Pre-Chorus"),
        ("Վերջերգ", "Outro"),
    ],
)
def test_armenian_section_names_become_suno_tags(tag, name):
    from ashugh.lyrics import suno_tag

    assert suno_tag(tag) == name


def test_an_armenian_loan_tag_takes_its_section_rule():
    rep = scan(
        "[Կուպլետ 1]\nԵս եմ տանը\n",
        from_dict({"language": "hy", "section": {"verse": {"syllables": 4}}}),
    )
    assert not any("matches no section" in i.message for i in rep.issues)


@pytest.mark.parametrize(
    "token,pieces",
    [("ՀՀ", ["Հա", "Հա"]), ("ԵՊՀ", ["Ե", "Պե", "Հա"]), ("ԱՄՆ", ["Ա", "Մե", "Նե"])],
)
def test_an_armenian_abbreviation_is_said_letter_by_letter(token, pieces):
    w = hy.analyze_word(token)
    assert [s.text for s in w.syllables] == pieces and w.spelled
    assert w.readings[0].stress == len(pieces) - 1


@pytest.mark.parametrize("token", ["ՀԱՊԿ", "ՆԱՏՕ", "Ես"])
def test_an_acronym_read_as_a_word_stays_a_word(token):
    assert not hy.analyze_word(token).spelled


def test_suno_spells_an_armenian_abbreviation():
    from ashugh import suno

    assert "Ա-Մե-Նե" in suno.format_song("Գնաց ԱՄՆ\n", tags=False).text
    out = suno.format_song("Գնաց ԱՄՆ\n", tags=False, armenian="latin").text
    assert "A-Me-Ne" in out
