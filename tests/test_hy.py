import pytest

from ashugh import lang
from ashugh.lang import hy

# Sung syllables of Eastern Armenian words, hidden schwas written out.
SUNG = {
    "Մկրտիչ": "Մը-կըր-տիչ",
    "սպասել": "ըս-պա-սել",
    "սկսել": "ըս-կը-սել",
    "ստվեր": "ըս-տը-վեր",
    "զգեստ": "ըզ-գեստ",
    "գրել": "գը-րել",
    "մնալ": "մը-նալ",
    "մտնել": "մըտ-նել",
    "նստել": "նըս-տել",
    "փնտրել": "փընտ-րել",
    "թռչուն": "թըռ-չուն",
    "կրծքով": "կըրծ-քով",
    "ձկնորս": "ձըկ-նորս",
    "Շնորհակալություն": "Շը-նոր-հա-կա-լու-թյուն",
    "Ադրբեջան": "Ա-դըր-բե-ջան",
    "Մկրտչյան": "Մը-կըրտ-չյան",
    "սիրտ": "սիրտ",
    "կյանք": "կյանք",
    "միտք": "միտք",
    "աչք": "աչք",
    "եղբայր": "եղ-բայր",
    "երկրորդ": "երկ-րորդ",
    "Աստված": "Աստ-ված",
    "տետր": "տե-տըր",
    "աստղ": "աս-տըղ",
    "մեղր": "մե-ղըր",
    "կայսր": "կայ-սըր",
    "սիրտս": "սիր-տըս",
    "սիրտդ": "սիր-տըդ",
    "գիրքս": "գիր-քըս",
    "գլուխս": "գը-լու-խըս",
    "Հայրս": "Հայ-րըս",
    "սիրտը": "սիր-տը",
    "ընկեր": "ըն-կեր",
    "Երևան": "Ե-րե-վան",
    "միևնույն": "մի-և-նույն",
    "Հայաստան": "Հա-յաս-տան",
    "միայն": "մի-այն",
}


@pytest.mark.parametrize("word,sung", SUNG.items())
def test_sung_syllables(word, sung):
    assert hy.analyze_word(word).sung() == sung


def test_capital_moves_onto_prothetic_schwa():
    assert hy.analyze_word("Սպասել").sung() == "Ըս-պա-սել"


@pytest.mark.parametrize(
    "word,stress",
    [("սպասել", 2), ("Մկրտիչ", 2), ("տետր", 0), ("սիրտը", 0), ("աստղ", 0), ("գլուխս", 1)],
)
def test_stress_is_last_full_vowel(word, stress):
    assert hy.analyze_word(word).readings[0].stress == stress


def test_stress_mark_moves_stress():
    assert hy.analyze_word("դու՛ք").readings[0].stress == 0
    assert hy.analyze_word("ի՛նչու").readings[0].stress == 0


def test_initial_e_and_o_get_glides():
    assert hy.analyze_word("երգ").readings[0].phones[:2] == ("j", "e")
    assert hy.analyze_word("որ").readings[0].phones[:2] == ("v", "o")
    assert hy.analyze_word("ով").readings[0].phones[0] == "o"
    assert hy.analyze_word("եմ").readings[0].phones[0] == "e"


def test_auxiliary_is_an_unstressed_enclitic():
    w = hy.analyze_word("էի")
    assert w.clitic and w.enclitic and w.readings[0].stress is None


def test_lexicon_override():
    w = hy.analyze_word("կայսրություն", {"կայսրություն": "կայ-սը-րու-թյուն"})
    assert w.sung() == "կայ-սը-րու-թյուն"
    assert w.readings[0].stress == 3


def test_prothetic_schwa_drops_after_a_vowel():
    words = lang.analyze("hy", ["նա", "ստացավ"], {})
    assert words[1].drop == 0
    words = lang.analyze("hy", ["ես", "ստացա"], {})
    assert words[1].drop is None


def test_final_schwa_links_onto_next_vowel():
    words = lang.analyze("hy", ["կյանքն", "է"], {})
    assert words[0].drop == 1
    words = lang.analyze("hy", ["լույսն", "ես"], {})
    assert words[0].drop == 1
    words = lang.analyze("hy", ["կյանքն", "կա"], {})
    assert words[0].drop is None


@pytest.mark.parametrize(
    "word,sung",
    [
        ("բոլորս", "բո-լո-րըս"),
        ("սերս", "սե-րըս"),
        ("յարս", "յա-րըս"),
        ("տունս", "տու-նըս"),
        ("անունս", "ա-նու-նըս"),
        ("անշտապ", "ան-շը-տապ"),
        ("անսպասելի", "ան-սը-պա-սե-լի"),
        ("անզգույշ", "ան-զը-գույշ"),
    ],
)
def test_possessive_after_sonorants_and_the_negative_prefix(word, sung):
    assert "-".join(s.text for s in hy.analyze_word(word).syllables) == sung


@pytest.mark.parametrize(
    "word,sung",
    [
        ("չորս", "չորս"),
        ("ներս", "ներս"),
        ("դուրս", "դուրս"),
        ("ձկնորս", "ձըկ-նորս"),
        ("Կարս", "Կարս"),
        ("լույս", "լույս"),
        ("հույս", "հույս"),
        ("մարդ", "մարդ"),
        ("վարդ", "վարդ"),
        ("ռոմանս", "ռո-մանս"),
        ("վալս", "վալս"),
        ("լեգենդ", "լե-գենդ"),
        ("ծնունդ", "ծը-նունդ"),
        ("սերունդ", "սե-րունդ"),
        ("խոստանալ", "խոս-տա-նալ"),
        ("հանգստանալ", "հան-գըս-տա-նալ"),
    ],
)
def test_words_that_end_or_cluster_like_that_without_a_schwa(word, sung):
    assert "-".join(s.text for s in hy.analyze_word(word).syllables) == sung
