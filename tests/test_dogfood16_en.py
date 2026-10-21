"""Round 16 of dogfooding, English: what a songwriter found wrong."""

import pytest

from ashugh import meter, rhyme
from ashugh.scan import analyze_lines, scan
from ashugh.spec import Spec, from_dict


def words(line: str, lang: str = "en"):
    (ln,) = analyze_lines(line, Spec(language=lang))
    return ln.words


def sizes(word: str) -> set[int]:
    w = words(word)[0]
    return {len(rhyme.nuclei(r.phones)) for r in w.readings}


def en_rhyme(a: str, b: str) -> float:
    lines = analyze_lines(f"{a}\n{b}", Spec(language="en"))
    return rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))[0]


def check(text: str, **spec):
    return scan(text, from_dict({"language": "en", **spec}))


@pytest.mark.parametrize(
    "word,n",
    [
        ("ev'ry", 2), ("ev'rything", 3), ("ev'ning", 2), ("sov'reign", 2), ("prob'ly", 2),
        ("fam'ly", 2), ("hist'ry", 2), ("diff'rent", 2), ("fav'rite", 2), ("gen'ral", 2),
        ("vict'ry", 2), ("cam'ra", 2), ("ev'ryone", 3), ("ev'rywhere", 3), ("choc'late", 2),
        ("bus'ness", 2), ("cath'lic", 2), ("temp'rance", 2), ("ling'ring", 2),
        ("list'ning", 2), ("sweet'ning", 2), ("pow'r", 1), ("heav'n", 1), ("wand'ring", 2),
        ("mem'ry", 2), ("flow'r", 1),
    ],
)  # fmt: skip
def test_an_apostrophe_leaves_out_one_vowel_of_the_full_word(word, n):
    assert sizes(word) == {n}


def test_a_hymn_line_with_evry_is_its_eight_syllables():
    assert not check("In ev'ry heart and ev'ry home\n", syllables=6).lines[0].ok
    assert check("In ev'ry heart and ev'ry home\n", syllables=8).lines[0].ok


@pytest.mark.parametrize(
    "word,shown",
    [("ev'ryone", "ev-ry-one"), ("ev'rywhere", "ev-ry-where"), ("whate'er", "what-e'er")],
)
def test_an_elided_word_is_shown_in_its_parts(word, shown):
    assert words(word)[0].sung() == shown


@pytest.mark.parametrize("word", ["whate'er", "where'er", "howe'er", "whene'er"])
def test_eer_is_ever_without_its_v(word):
    assert sizes(word) == {2}


def test_whateer_rhymes_with_there():
    assert en_rhyme("whate'er", "there") >= rhyme.THRESHOLD["perfect"]


@pytest.mark.parametrize("word", ["e'er", "ne'er", "o'er", "e'en"])
def test_a_one_syllable_elision_stays_one(word):
    assert sizes(word) == {1}


def test_thee_leans_on_its_verb():
    text = "O Lord, we come to praise thee\nWith all our voice we raise thee\n"
    report = check(text, meter="iamb", feet=3, rhyme="AA")
    assert all(lr.ok for lr in report.lines), [i.message for i in report.issues]


def test_two_verbs_before_thee_do_not_rhyme():
    assert en_rhyme("praise thee", "love thee") < rhyme.THRESHOLD["near"]
    text = "O Lord, we come to praise thee\nWith all our hearts we love thee\n"
    assert any(i.code == "rhyme" for i in check(text, rhyme="AA").issues)


@pytest.mark.parametrize(
    "text",
    [
        "I humbly bow before you\nForever I adore you\n",
        "There's nothing left between us\nNo light from distant Venus\n",
    ],
)
def test_a_pronoun_leans_on_a_two_syllable_preposition(text):
    report = check(text, meter="iamb", feet=3, rhyme="AA")
    assert all(lr.ok for lr in report.lines), [i.message for i in report.issues]


def test_under_me_rhymes_with_thunder_me():
    text = "The storm clouds gather, thunder me\nThe ground is breaking under me\n"
    assert all(lr.ok for lr in check(text, rhyme="AA").lines)


@pytest.mark.parametrize(
    "text",
    [
        "You play me like a broken record\nThe only song that I adored\n",
        "Put on the old record\nThe crowd adored\n",
        "We cross the burning desert\nForever alert\n",
        "I gave my sweetest present\nTo you who still resent\n",
        "I hear the howling wind\nAnd you were never kind\n",
    ],
)
def test_a_noun_stays_a_noun_past_its_adjective(text):
    assert any(i.code == "rhyme" for i in check(text, rhyme="AA").issues)


@pytest.mark.parametrize(
    "text",
    [
        "I hear the howling wind\nAnd now I've sinned\n",
        "We will record\nThe songs we adored\n",
        "I want to present\nThe gift that I meant\n",
    ],
)
def test_the_reading_its_context_allows_still_rhymes(text):
    assert not any(i.code == "rhyme" for i in check(text, rhyme="AA").issues)


def test_burns_is_english():
    text = (
        "Wee, sleekit, cow'rin, tim'rous beastie,\nO, what a panic's in thy breastie!\n"
        "Thou need na start awa sae hasty,\nWi' bickering brattle!\n"
        "I wad be laith to rin an' chase thee,\nWi' murd'ring pattle!\n"
    )
    report = scan(text)
    assert all(lr.line.lang == "en" for lr in report.lines)


@pytest.mark.parametrize(
    "line",
    [
        "Ari ari im anush yar",
        "Kez em sirum du im kyanqn es",
        "Du im kyanqn es",
        "Ari mot, yars, chem karogh aranc qez aprel",
        "T'agavor u ch'em gnum",
    ],
)
def test_latin_typed_armenian_is_still_found(line):
    from ashugh.lang import latin_armenian
    from ashugh.lyrics import tokenize

    assert latin_armenian(tokenize(line))
