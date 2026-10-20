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


@pytest.mark.parametrize("word", ["այն", "նրան", "կարմիր", "ձայն"])
def test_other_final_sonorant_pairs_stay_closed(word):
    assert all("ը" not in s.text for s in hy.analyze_word(word).syllables[-1:])


@pytest.mark.parametrize("word", ["սարն", "դարն", "տունն"])
def test_the_article_n_after_a_sonorant_has_an_optional_schwa(word):
    w = hy.analyze_word(word)
    assert w.drop == w.optional == w.size - 1 and "article" in w.optional_why


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


@pytest.mark.parametrize(
    "word,want",
    [
        ("մեղադրել", "մե-ղա-դը-րել"),
        ("մեղադրանքը", "մե-ղա-դը-րան-քը"),  # an inflection the dictionary does not list
        ("ախտանշանը", "ախ-տա-նը-շա-նը"),
        ("նախագծել", "նա-խա-գը-ծել"),
        ("անհրաժեշտ", "ան-հը-րա-ժեշտ"),
        ("անհրաժեշտություն", "ան-հը-րա-ժեշ-տու-թյուն"),
        ("Մեղադրեց", "Մե-ղա-դը-րեց"),
    ],
)
def test_compounds_keep_their_second_roots_schwa(word, want):
    assert sung(word) == want


@pytest.mark.parametrize(
    "word,want",
    [
        ("կերակրել", "կե-րակ-րել"),  # Wiktionary has it with and without the schwa
        ("աշխարհ", "աշ-խարհ"),
        ("մանկություն", "ման-կու-թյուն"),
        ("Մկրտիչ", "Մը-կըր-տիչ"),
        ("ազատություն", "ա-զա-տու-թյուն"),
    ],
)
def test_other_medial_clusters_are_left_to_the_rules(word, want):
    assert sung(word) == want


def test_the_compound_list_is_loaded():
    keys = hy.compound_schwas()
    assert "մեղադր" in keys and len(keys) > 150
    assert all(len(k) >= hy.MIN_COMPOUND for k in keys)


def test_a_compounds_schwa_is_optional():
    w = hy.analyze_word("լուսանկար")
    assert sung("լուսանկար") == "լու-սա-նը-կար"
    assert w.optional == 2 and w.drop == 2
    assert hy.analyze_word("Մկրտիչ").optional is None  # a cluster's schwa is not


def _scan(text, **rule):
    from ashugh.scan import scan
    from ashugh.spec import from_dict

    return scan(text, from_dict({"language": "hy", **rule}))


def test_a_line_fits_with_or_without_the_compounds_schwa():
    line = "Լուսանկարներ պատին կախված\n"
    rep = _scan(line, meter="iamb4")
    assert [i for i in rep.issues if i.severity == "error"] == []
    assert rep.units[0].lines[0].sung.startswith("Լու-սա-ն(ը)-կար-ներ")
    assert _scan("Լուսանկարներ\n", syllables=5).ok  # sung with it
    short = _scan("Լուսանկարներ\n", syllables=4)  # or without
    assert short.ok
    (note,) = [i for i in short.issues if i.code == "syllables"]
    assert "Լուսանկարներ" in note.message and "second root" in note.detail
    assert not _scan("Լուսանկարներ\n", syllables=3).ok


@pytest.mark.parametrize(
    "word,want",
    [
        ("Մինսկ", "Մինսկ"),
        ("Կուրսկ", "Կուրսկ"),
        ("Օմսկ", "Օմսկ"),
        ("տեքստ", "տեքստ"),
        ("կոնտեքստ", "կոն-տեքստ"),
        ("պարտք", "պարտք"),
        ("կուրծք", "կուրծք"),
        ("անցք", "անցք"),
        ("միջանցք", "մի-ջանցք"),
        ("համայնք", "հա-մայնք"),
        ("շնորհք", "շը-նորհք"),
        ("Մարքս", "Մարքս"),
        ("ցանքս", "ցանքս"),
    ],
)
def test_a_final_cluster_falling_in_sonority_is_one_coda(word, want):
    assert sung(word) == want  # Wiktionary: minsk, tekʰst, pɑɾtkʰ, kuɾt͡skʰ, mɑɾkʰs


@pytest.mark.parametrize(
    "word,want",
    [
        ("աստղ", "աս-տըղ"),
        ("բարձր", "բար-ձըր"),
        ("ոսկր", "ոս-կըր"),
        ("այժմ", "այ-ժըմ"),
        ("արկղ", "ար-կըղ"),
        ("կայսր", "կայ-սըր"),
        ("սիրտս", "սիր-տըս"),
        ("կյանքս", "կյան-քըս"),
        ("վերջերքս", "վեր-ջեր-քըս"),
    ],
)
def test_a_final_cluster_rising_at_its_end_or_a_possessive_keeps_its_schwa(word, want):
    assert sung(word) == want


@pytest.mark.parametrize(
    "word,want",
    [
        ("զրնգալ", "զը-րըն-գալ"),
        ("բռնկել", "բը-ռըն-կել"),
        ("դռնփակ", "դը-ռըն-փակ"),
        ("խլրտալ", "խը-լըր-տալ"),
        ("բլնգազ", "բը-լըն-գազ"),
        ("բժշկել", "բը-ժըշ-կել"),
    ],
)
def test_a_schwa_syllable_closes_on_two_consonants_only_if_the_second_is_a_stop(word, want):
    assert sung(word) == want  # Wiktionary: zəɾənɡɑl, bərənkel, bəʒəʃkel


@pytest.mark.parametrize(
    "word,want",
    [
        ("Մկրտչյան", "Մը-կըրտ-չյան"),
        ("Հնդկաստան", "Հընդ-կաս-տան"),
        ("թռչնակ", "թըռչ-նակ"),
        ("գրտնակ", "գըրտ-նակ"),
        ("խնդրել", "խընդ-րել"),
    ],
)
def test_a_schwa_syllable_may_close_on_a_sonorant_and_a_stop(word, want):
    assert sung(word) == want  # məkəɾttʃʰjɑn, həndkɑstɑn, tʰərtʃʰnɑk


@pytest.mark.parametrize(
    "word,want",
    [
        ("լուսանշան", "լու-սա-նը-շան"),
        ("թվանշան", "թը-վա-նը-շան"),
        ("բենզասղոց", "բեն-զա-սը-ղոց"),
        ("ցուցանմուշ", "ցու-ցա-նը-մուշ"),
        ("գանգրանման", "գանգ-րա-նը-ման"),
    ],
)
def test_a_compounds_second_root_keeps_the_schwa_it_opens_with(word, want):
    w = hy.analyze_word(word)
    assert sung(word) == want and w.optional is not None  # from նշան, սղոց, նմուշ, նման


@pytest.mark.parametrize("word", ["համագործակցել", "ուղեկցորդ", "էլեկտրոն", "պատկեր"])
def test_a_root_that_breaks_a_dictionary_word_is_not_listed(word):
    assert all(not s.epenthetic for s in hy.analyze_word(word).syllables[1:])


def test_a_root_listed_opens_on_a_cluster_with_its_schwa_inside():
    roots = hy.cluster_roots()
    assert {"նշան", "սղոց", "նմուշ"} <= roots
    assert not any(r.startswith(("ստ", "սպ", "զգ", "շտ")) for r in roots)  # ըս-տեղ-ծել
    assert "կցել" not in roots  # it would break համագործակցել


@pytest.mark.parametrize(
    "word,want",
    [("կողմ", "կողմ"), ("մեղմ", "մեղմ"), ("կազմ", "կազմ"), ("ռեալիզմ", "ռե-ա-լիզմ")],
)
def test_a_word_may_end_on_a_fricative_and_m(word, want):
    assert sung(word) == want  # Wiktionary: all 84 such entries closed (koʁm, ɾeɑlizm)


@pytest.mark.parametrize(
    "word,want", [("դաշն", "դա-շըն"), ("դյուցազն", "դյու-ցա-զըն"), ("ծանր", "ծա-նըր")]
)
def test_a_fricative_and_n_or_a_sonorant_and_r_keep_the_schwa(word, want):
    assert sung(word) == want  # 14 of 17 fricative + ն entries split
