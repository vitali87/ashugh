"""Round 13 of dogfooding, Armenian: what a songwriter found wrong."""

import pytest

from ashugh import suno
from ashugh.lang import hy
from ashugh.scan import analyze_lines
from ashugh.spec import Spec


def words(line: str):
    (ln,) = analyze_lines(line, Spec(language="hy"))
    return ln.words


def shown(w) -> str:
    return "-".join(s.text for s in w.syllables)


@pytest.mark.parametrize(
    "token, pieces",
    [
        ("ԱՄՆ-ից", "Ա-Մե-Նե-ից"),
        ("ԵՊՀ-ից", "Ե-Պե-Հա-յից"),
        ("ՀՀ-ի", "Հա-Հա-յի"),
        ("ՀՀԿ-ն", "Հա-Հա-Կան"),
        ("ԱՄՆ-ում", "Ա-Մե-Նե-ում"),
    ],
)
def test_an_abbreviation_with_a_case_ending_is_spelt_and_takes_it(token, pieces):
    (w,) = words(token)
    assert w.spelled and shown(w) == pieces
    assert w.readings[0].stress == w.size - 1  # the ending, as Armenian stresses the end


@pytest.mark.parametrize("token", ["Երևան-Գյումրի", "ՆԱՏՕ-ի", "ԱՄՆ-Ռուսաստան"])
def test_other_hyphenated_words_are_no_spelt_abbreviation(token):
    assert not words(token)[0].spelled


def test_suno_writes_the_ending_after_the_letters():
    out = suno.format_song("ԱՄՆ-ից, ՀՀ-ի\n", tags=False, armenian="latin").text
    assert "A-Me-Ne-its" in out and "Ha-Ha-yi" in out


def test_a_vowelless_abbreviation_is_spelt_in_a_line_in_capitals():
    w = words("ՀՀ ՀԱՅԱՍՏԱՆ")
    assert w[0].spelled and w[0].size == 2 and not w[1].spelled


def test_a_syllable_count_counts_the_letters():
    assert sum(w.size for w in words("Ես եկա ԱՄՆ-ից քեզ մոտ")) == 9


def test_analyze_word_alone():
    assert hy.analyze_word("ՀՀ-ի").size == 3


@pytest.mark.parametrize(
    "line, k, size, stress",
    [
        ("Ասում ա՝ Ararat-ը սիրում եմ ես", 2, 4, 2),  # a-ra-rat-ը: never on ը
        ("Տեսա TikTok-ում", 1, 3, 2),  # tik-tok-ում, the ending stressed
        ("Facebook-ից եկավ", 0, 3, 2),
        ("Իմ iPhone-ս", 1, 3, 1),  # i-phone-ըս: the possessive's schwa after a consonant
        ("Իմ Gucci-ն", 1, 2, 1),  # after a vowel the article is a coda
    ],
)
def test_a_latin_name_with_an_armenian_ending(line, k, size, stress):
    w = words(line)[k]
    assert w.lang == "hy" and (w.size, w.readings[0].stress) == (size, stress)


def test_a_latin_line_of_names_with_endings_keeps_them():
    ws = words("TikTok-ում, YouTube-ում, Facebook-ում")
    assert [w.size for w in ws] == [3, 3, 3]


@pytest.mark.parametrize(
    "line, mode, out",
    [
        ("Տեսա TikTok-ում\n", "latin", "TikTok-um"),
        ("Ասում ա՝ Ararat-ը սիրում եմ ես\n", "latin", "Ararat-ə"),
        ("Տեսա TikTok-ում\n", "script", "TikTok-ում"),
        ("Տեսա TikTok-ում\n", "schwa", "TikTok-ում"),
        ("TikTok-ում, YouTube-ում\n", "latin", "TikTok-um, YouTube-um"),
    ],
)
def test_suno_keeps_the_name_and_writes_the_ending(line, mode, out):
    assert out in suno.format_song(line, tags=False, armenian=mode).text


@pytest.mark.parametrize(
    "latin, script",
    [("sirum em", "սիրում եմ"), ("spasum es", "սպասում ես"), ("gnum enq", "գնում ենք")],
)
def test_a_latin_typed_auxiliary_is_the_auxiliary(latin, script):
    def stresses(line):
        return [w.readings[0].stress for w in words(line)]

    assert stresses(latin) == stresses(script)
    assert words(latin)[1].clitic


def test_a_latin_typed_auxiliary_is_no_rhyme_word():
    from ashugh import meter, rhyme

    lines = analyze_lines("sirum em\ntem chem", Spec(language="hy"))
    ts = [rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines]
    assert rhyme.match(*ts)[0] < rhyme.THRESHOLD["near"]


@pytest.mark.parametrize(
    "word, armenian", [("em", "եմ"), ("es", "ես"), ("enq", "ենք"), ("eq", "եք"), ("en", "են")]
)
def test_from_latin_reads_the_auxiliaries_whole(word, armenian):
    assert hy.from_latin(word) == armenian


def test_other_latin_words_in_e_keep_their_e():
    assert hy.from_latin("ergum") == "էրգում"


@pytest.mark.parametrize("line", ["Ուր ես, ես կգամ", "Ուր ես։ Ես կգամ", "Ով ես, ես գիտեմ"])
def test_an_auxiliary_es_that_ends_its_clause_stays_the_auxiliary(line):
    ws = words(line)
    assert ws[1].clitic and not ws[2].clitic


def test_suno_writes_the_clause_final_auxiliary_as_es():
    out = suno.format_song("Ուր ես, ես կգամ\n", tags=False, armenian="latin").text
    assert out.startswith("Ur es, yes")


@pytest.mark.parametrize("line", ["Սիրում եմ ես, դու գիտես", "Հիմա ես գիտեմ"])
def test_the_pronoun_es_stays_the_pronoun(line):
    ws = words(line)
    k = [w.norm for w in ws].index("ես")
    assert not ws[k].clitic
