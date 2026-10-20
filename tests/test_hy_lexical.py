"""Armenian final clusters checked against Wiktionary's pronunciations."""

import pytest

from ashugh.lang import hy


def sung(word: str) -> str:
    return "-".join(s.text for s in hy.analyze_word(word).syllables)


@pytest.mark.parametrize(
    "word,want",
    [
        ("ուրեմն", "ու-րե-մըն"),
        ("երբեմն", "եր-բե-մըն"),
        ("հիմն", "հի-մըն"),
        ("ոմն", "ո-մըն"),
        ("սառն", "սա-ռըն"),
        ("դառն", "դա-ռըն"),
        ("բուռն", "բու-ռըն"),
        ("ձեռն", "ձե-ռըն"),
    ],
)
def test_final_mn_and_rn_take_a_schwa(word, want):
    assert sung(word) == want


@pytest.mark.parametrize("word", ["այն", "նրան", "կարմիր", "սարն", "դարն", "ձայն", "տունն"])
def test_other_final_sonorant_pairs_stay_closed(word):
    assert all("ը" not in s.text for s in hy.analyze_word(word).syllables[-1:])


@pytest.mark.parametrize(
    "word,want",
    [
        ("սերդ", "սե-րըդ"),
        ("ընկերդ", "ըն-կե-րըդ"),
        ("դուռդ", "դու-ռըդ"),
        ("հյուրդ", "հյու-րըդ"),
        ("աչքերդ", "աչ-քե-րըդ"),
    ],
)
def test_possessive_d_after_r(word, want):
    assert sung(word) == want


@pytest.mark.parametrize(
    "word,want",
    [
        ("մարդ", "մարդ"),
        ("վարդ", "վարդ"),
        ("բերդ", "բերդ"),
        ("ժողովուրդ", "ժո-ղո-վուրդ"),
        ("երիտասարդ", "ե-րի-տա-սարդ"),
        ("վարորդ", "վա-րորդ"),
        ("հինգերորդ", "հին-գե-րորդ"),
        ("քսանհինգերորդ", "քը-սան-հին-գե-րորդ"),
        ("միջնաբերդ", "միջ-նա-բերդ"),
        ("տղամարդ", "տը-ղա-մարդ"),
        ("դափնեվարդ", "դափ-նե-վարդ"),
        ("բուրդ", "բուրդ"),
        ("նյարդ", "նյարդ"),
    ],
)
def test_lexical_rd_stays_closed(word, want):
    assert sung(word) == want


@pytest.mark.parametrize(
    "word,want",
    [
        ("ադամանդ", "ա-դա-մանդ"),
        ("անդունդ", "ան-դունդ"),
        ("բնազդ", "բը-նազդ"),
        ("գովազդ", "գո-վազդ"),
        ("խեղդ", "խեղդ"),
        ("նորահարս", "նո-րա-հարս"),
        ("դեղատոմս", "դե-ղա-տոմս"),
        ("ծախս", "ծախս"),
        ("մաքս", "մաքս"),
    ],
)
def test_lemmas_ending_like_a_possessive_are_lexical(word, want):
    assert sung(word) == want


@pytest.mark.parametrize(
    "word,want",
    [
        ("մազերդ", "մա-զե-րըդ"),  # not like զերդ
        ("համարդ", "հա-մա-րըդ"),  # not like մարդ
        ("տներս", "տը-նե-րըս"),  # not like ներս
        ("անուններս", "ա-նուն-նե-րըս"),
        ("յարդ", "յա-րըդ"),  # your beloved, not straw
        ("տունդ", "տու-նըդ"),
        ("ձայնդ", "ձայ-նըդ"),
        ("ջանդ", "ջա-նըդ"),
        ("աչքս", "աչ-քըս"),
        ("ձեռքս", "ձեռ-քըս"),
        ("սերս", "սե-րըս"),
        ("դեմքդ", "դեմ-քըդ"),
    ],
)
def test_possessives_still_take_their_schwa(word, want):
    assert sung(word) == want


def test_the_lexicon_is_loaded_and_lowercase():
    words = hy.lexical_endings()
    assert len(words) > 200
    assert "ադամանդ" in words and "մարդ" in words
    assert all(w == w.lower() for w in words)


@pytest.mark.parametrize("word,want", [("խորհուրդ", "խոր-հուրդ"), ("աբսուրդ", "աբ-սուրդ")])
def test_nouns_in_urd_are_lexical(word, want):
    assert sung(word) == want


@pytest.mark.parametrize("word,want", [("ջուրդ", "ջու-րըդ"), ("սուրդ", "սու-րըդ")])
def test_short_words_in_urd_are_possessive(word, want):
    assert sung(word) == want
