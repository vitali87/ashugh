"""Round 16 of dogfooding, Armenian: what a songwriter found wrong."""

import pytest

from ashugh import meter, rhyme
from ashugh.scan import analyze_lines, scan
from ashugh.spec import Spec, from_dict


def words(line: str, lang: str = "hy"):
    (ln,) = analyze_lines(line, Spec(language=lang))
    return ln.words


def sung(word: str) -> str:
    return words(word)[0].sung()


def hy_rhyme(a: str, b: str) -> float:
    lines = analyze_lines(f"{a}\n{b}", Spec(language="hy"))
    return rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))[0]


@pytest.mark.parametrize(
    "word,shown",
    [
        ("չգնաց", "չը-գը-նաց"), ("չմնաց", "չը-մը-նաց"), ("չլսեց", "չը-լը-սեց"),
        ("չգրեց", "չը-գը-րեց"), ("չթռավ", "չը-թը-ռավ"), ("չգնալու", "չը-գը-նա-լու"),
        ("չմտածեց", "չը-մը-տա-ծեց"), ("չգնացի", "չը-գը-նա-ցի"),
    ],
)  # fmt: skip
def test_the_negative_keeps_its_stems_schwa_in_the_aorist_and_participle(word, shown):
    assert sung(word) == shown


@pytest.mark.parametrize(
    "word,shown",
    [
        ("կգտնեմ", "կը-գըտ-նեմ"), ("կմտնեմ", "կը-մըտ-նեմ"), ("չմտնես", "չը-մըտ-նես"),
        ("կկտրեմ", "կը-կըտ-րեմ"), ("կկպնեմ", "կը-կըպ-նեմ"), ("կգտնի", "կը-գըտ-նի"),
    ],
)  # fmt: skip
def test_a_prefix_before_a_three_consonant_stem_keeps_the_stems_schwa(word, shown):
    assert sung(word) == shown


@pytest.mark.parametrize(
    "word,shown",
    [
        ("կգրեմ", "կը-գը-րեմ"),
        ("կգրի", "կը-գը-րի"),
        ("կգրեիր", "կը-գը-րե-իր"),
        ("կկրեմ", "կը-կը-րեմ"),
    ],
)
def test_the_future_of_grel_and_krel(word, shown):
    assert sung(word) == shown


@pytest.mark.parametrize("word,shown", [("չնչին", "չըն-չին"), ("կծծի", "կըծ-ծի")])
def test_roots_that_only_look_prefixed_stay(word, shown):
    assert sung(word) == shown


@pytest.mark.parametrize(
    "word,shown",
    [
        ("անշնորհք", "ան-շը-նորհք"), ("անսխալ", "ան-սը-խալ"), ("անխռով", "ան-խը-ռով"),
        ("անգթություն", "ան-գը-թու-թյուն"), ("անխնա", "ան-խը-նա"), ("անսեր", "ան-սեր"),
    ],
)  # fmt: skip
def test_the_negative_an_keeps_its_roots_schwa(word, shown):
    assert sung(word) == shown


@pytest.mark.parametrize(
    "word,shown",
    [
        ("քսանչորս", "քը-սան-չորս"), ("երեսունչորս", "ե-րե-սուն-չորս"),
        ("քառասունչորս", "քա-ռա-սուն-չորս"), ("գերմարդ", "գեր-մարդ"), ("տասնչորս", "տաս-նը-չորս"),
    ],
)  # fmt: skip
def test_a_compound_numeral_takes_no_possessive_schwa(word, shown):
    assert sung(word) == shown


@pytest.mark.parametrize(
    "word,shown",
    [
        ("Աստուած", "Աստ-ված"), ("անցեալ", "ան-ցյալ"), ("ուրախութեամբ", "ու-րա-խու-թյամբ"),
        ("մանեակ", "մա-նյակ"), ("սեաւ", "սև"), ("հայեացք", "հա-յացք"), ("արուեստ", "ար-վեստ"),
        ("թիւ", "թիվ"), ("հաշիւ", "հա-շիվ"), ("հիմայ", "հի-մա"), ("կայ", "կա"), ("չկայ", "չը-կա"),
        ("յոյս", "հույս"), ("յետոյ", "հե-տո"), ("կեանք", "կյանք"), ("ձիւն", "ձյուն"),
    ],
)  # fmt: skip
def test_classical_spelling_is_read_reformed(word, shown):
    assert sung(word).lower() == shown.lower()


@pytest.mark.parametrize(
    "word,shown",
    [
        ("Կորեայում", "Կո-րե-ա-յում"), ("սեանս", "սե-անս"), ("Նեանդերթալ", "Նե-ան-դեր-թալ"),
        ("ռեալ", "ռե-ալ"), ("իդեալ", "ի-դե-ալ"), ("Նոյ", "Նոյ"), ("Նիկոլայ", "Նի-կո-լայ"),
        ("յուղ", "յուղ"), ("դուետ", "դու-ետ"),
    ],
)  # fmt: skip
def test_a_loan_or_name_is_not_read_as_classical(word, shown):
    assert sung(word) == shown


def test_a_classical_rhyme_rhymes_as_it_is_said():
    assert hy_rhyme("հիմայ", "Ռիմա") >= rhyme.THRESHOLD["perfect"]


def test_a_lexicon_entry_may_give_a_classical_word_its_reformed_syllables():
    spec = from_dict({"language": "hy", "lexicon": {"Աստուած": "Աստ-ված"}})
    report = scan("Աստուած սեաւ\n", spec)
    assert report.lines[0].fit.count == 3 and not report.issues
