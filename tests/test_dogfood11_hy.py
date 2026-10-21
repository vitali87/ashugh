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


@pytest.mark.parametrize(
    "line,low",
    [("քո ստվերն է", 4), ("քո սպասումն է", 4)],
)
def test_a_word_may_lose_its_leading_schwa_and_link_its_last(line, low):
    ws = words(line)
    assert sum(w.size for w in ws) - 1 == low  # the linking ը may drop too


def test_an_eight_syllable_line_with_both_schwas_fits_eight():
    rep = scan("Քո ստվերն է մնում ինձ հետ\n", from_dict({"language": "hy", "syllables": 8}))
    assert not [i for i in rep.issues if i.severity == "error"]


def test_suno_without_a_spec_swallows_a_leading_schwa_after_a_vowel():
    from ashugh import suno

    assert "Na statsav" in suno.format_song("Նա ստացավ\n", tags=False, armenian="latin").text
    assert (
        "U spasum"
        in suno.format_song("Ու սպասում է քեզ նորից\n", tags=False, armenian="latin").text
    )


@pytest.mark.parametrize(
    "latin,script",
    [
        ("Mtnem", "մտնեմ"),
        ("spasum", "սպասում"),
        ("kyanq", "կյանք"),
        ("hrashq", "հրաշք"),
        ("qaghem", "քաղեմ"),
        ("vard", "վարդ"),
        ("yes", "ես"),
        ("vor", "որ"),
        ("sirum", "սիրում"),
        ("chem", "չեմ"),
        ("aghjik", "աղջիկ"),
        ("Yerevan", "երեվան"),  # եվ before a vowel, as Եվրոպա; Երևան reads the same
        ("Sevan", "սեվան"),
        ("ev", "և"),
    ],
)
def test_latin_armenian_is_read_in_armenian_letters(latin, script):
    assert hy.from_latin(latin) == script


def test_a_latin_armenian_line_counts_armenian_syllables():
    ws = words("Mtnem aygin, qaghem vard")
    assert [w.size for w in ws] == [2, 2, 2, 1]
    assert ws[0].text == "Mtnem" and ws[0].lang == "hy"


def test_an_english_line_in_an_armenian_song_stays_english():
    ws = words("I love you so")
    assert all(w.lang == "en" for w in ws)


def test_latin_armenian_rhymes_by_its_sounds():
    a, b = words("kyanq")[0], words("hrashq")[0]
    assert a.readings[0].phones[-1] == b.readings[0].phones[-1] == "kʰ"  # Armenian, not English k


@pytest.mark.parametrize(
    "line",
    ["Ari ari im anush yar", "Kez em sirum du im kyanqn es", "Yerevan Yerevan im sirun qaghaq"],
)
def test_latin_armenian_lines_are_recognised(line):
    assert all(w.lang == "hy" for w in words(line))


@pytest.mark.parametrize(
    "line", ["I love you baby", "Midnight city lights", "Dance with me tonight"]
)
def test_english_lines_in_an_armenian_song_are_not(line):
    assert all(w.lang == "en" for w in words(line))
