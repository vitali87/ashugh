"""Round five of dogfooding: RIFMA's errors and three expert users."""

import pytest

from ashugh.lang import ru


def stressed(word: str) -> list[int | None]:
    return ru.analyze_word(word).stress_options()


@pytest.mark.parametrize(
    "word,want",
    [
        ("кому", [1]),
        ("никого", [2]),
        ("никому", [2]),
        ("никем", [1]),
        ("некому", [0]),
        ("нечему", [0]),
        ("некем", [0]),
        ("нечем", [0]),
    ],
)
def test_forms_of_kto_and_chto(word, want):
    assert stressed(word) == want  # кому́, never ко́му (of ком, a lump)


@pytest.mark.parametrize(
    "word,want",
    [("стараясь", [1]), ("боясь", [1]), ("улыбаясь", [2]), ("держась", [1]), ("смеясь", [1])],
)
def test_a_gerund_in_sь_takes_its_verbs_stress(word, want):
    assert stressed(word) == want  # стара́ясь from стара́юсь, not ста́раясь from ста́рая


@pytest.mark.parametrize("word,want", [("умылась", [1]), ("взялась", [1]), ("старался", [1])])
def test_a_past_form_in_sя_still_reads_like_its_plain_form(word, want):
    assert stressed(word) == want


@pytest.mark.parametrize("word", ["пенье", "пенья", "пенью", "пеньем"])
def test_penye_is_the_song_form_of_penie(word):
    assert stressed(word) == [0]  # пе́нье, as пе́ние; not пенье́ of пеньё (stumps)


def en_rhyme(a: str, b: str) -> float:
    from ashugh import meter, rhyme
    from ashugh.scan import analyze_lines
    from ashugh.spec import Spec

    lines = analyze_lines(f"{a}\n{b}", Spec(language="en"), "en")
    return rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))[0]


def test_an_object_pronoun_after_a_verb_leans_on_it():
    from ashugh.scan import scan
    from ashugh.spec import from_dict

    rep = scan(
        "Money, honey, I don't need it\n", from_dict({"language": "en", "meter": "trochee4"})
    )
    assert [i.code for i in rep.issues if i.severity == "error"] == []
    assert rep.units[0].lines[0].fit.ending == 1  # NEED it


def test_lines_ending_on_the_same_pronoun_rhyme_on_the_word_before():
    from ashugh import rhyme

    assert en_rhyme("I don't need it", "I don't want it") < rhyme.THRESHOLD["slant"]
    assert en_rhyme("I don't need it", "I can feel it") >= rhyme.THRESHOLD["slant"]
    assert en_rhyme("so hold me", "you told me") >= rhyme.THRESHOLD["perfect"]


def test_a_leaning_pronoun_may_still_carry_the_rhyme():
    from ashugh import rhyme

    assert en_rhyme("you know I love you", "I'll always be true") >= rhyme.THRESHOLD["perfect"]


def test_after_a_preposition_the_pronoun_keeps_its_stress():
    from ashugh.scan import scan
    from ashugh.spec import from_dict

    rep = scan("I'm waiting here for you\n", from_dict({"language": "en", "meter": "iamb3"}))
    assert rep.units[0].lines[0].fit.ending == 0


def test_an_ending_asked_by_the_rhymes_case_says_so():
    from ashugh.scan import scan
    from ashugh.spec import from_dict

    rep = scan("I walk the way\nI hold the light\n", from_dict({"language": "en", "rhyme": "Ab"}))
    (issue,) = [i for i in rep.issues if i.code == "ending"]
    assert issue.line == 1 and "capital A" in issue.detail and "feminine" in issue.detail
