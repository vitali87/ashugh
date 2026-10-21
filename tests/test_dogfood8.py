"""False passes found by the eighth dogfooding round: wrong lines ashugh accepted."""

import pytest

from ashugh.lang import en, ru
from ashugh.scan import scan
from ashugh.spec import from_dict


def meter_errors(text: str, **spec) -> list[str]:
    rep = scan(text, from_dict(spec))
    return [i.message for i in rep.issues if i.severity == "error"]


@pytest.mark.parametrize(
    "line",
    [
        "A new program runs through the night",
        "The young athlete swims in the bay",
        "A small insect sleeps in the light",
        "My old comrade sails far away",
        "A pale vampire sleeps by the bay",
    ],
)
def test_a_word_that_is_no_compound_keeps_its_stress(line):
    errors = meter_errors(line + "\n", language="en", meter="iamb4")
    assert any("off the beat" in e for e in errors), errors


@pytest.mark.parametrize("word", ["sometime", "moonlight", "heartache", "birdhouse"])
def test_a_compound_may_still_shift_onto_its_second_part(word):
    assert 1 in en.analyze_word(word).stress_options()


def level(a: str, b: str, capsys) -> str:
    from ashugh.cli import main

    main(["rhyme", a, b])
    return capsys.readouterr().out.split()[0]


@pytest.mark.parametrize(
    "a, b",
    [("still", "feel"), ("sit", "seat"), ("ship", "sheep"), ("river", "fever"),
     ("far", "war"), ("door", "car"), ("born", "barn"), ("more", "are")],
)  # fmt: skip
def test_english_kit_fleece_and_north_start_do_not_rhyme(a, b, capsys):
    assert level(a, b, capsys) == "none"


@pytest.mark.parametrize(
    "a, b, want",
    [("law", "saw", "perfect"), ("caught", "cot", "perfect"), ("dawn", "con", "perfect"),
     ("door", "four", "perfect"), ("sea", "me", "perfect"),
     # before r English keeps no KIT / FLEECE contrast, whatever CMUdict writes
     ("here", "year", "perfect"), ("pier", "here", "perfect"), ("clear", "fear", "perfect"),
     ("tour", "poor", "perfect"), ("sure", "pure", "perfect")],
)  # fmt: skip
def test_english_vowels_that_do_rhyme_still_do(a, b, want, capsys):
    assert level(a, b, capsys) == want


def test_kit_fleece_breaks_a_stanza():
    text = (
        "The harbor lights are burning still,\nThe boats are sleeping, near and far,\n"
        "And every sailor's heart can feel\nThe drums that call him to the war.\n"
    )
    errors = meter_errors(text, language="en", meter="iamb4", rhyme="ABAB")
    assert sum("rhyme" in e for e in errors) == 2, errors


@pytest.mark.parametrize(
    "word, stress",
    [("кормящая", 1), ("ходящий", 1), ("носящих", 1), ("держащий", 1), ("просящий", 1),
     ("платящий", 1), ("любящий", 0), ("лечащий", 0), ("дышащий", 0), ("пишущий", 0),
     ("колющий", 0)],
)  # fmt: skip
def test_a_derived_participle_takes_its_normative_stress(word, stress):
    assert ru.analyze_word(word).readings[0].stress == stress


def test_a_misstressed_participle_breaks_the_iamb():
    text = "Я жду тебя у старой двери,\nИ кормящая мать не верит,\n"
    errors = meter_errors(text, language="ru", meter="iamb4")
    assert any("off the beat" in e for e in errors), errors


@pytest.mark.parametrize("word, stress", [("сверлит", 1), ("сверлишь", 1), ("мастерски", 2)])
def test_dictionary_stresses_the_dump_gets_wrong(word, stress):
    assert ru.analyze_word(word).stress_options() == [stress]


@pytest.mark.parametrize("word, stress", [("кремень", 1), ("ненависть", 0)])
def test_dictionary_stresses_the_dump_gets_right(word, stress):
    assert ru.analyze_word(word).stress_options() == [stress]  # креме́нь, не́нависть


def test_both_stresses_of_znachimost():
    assert set(ru.analyze_word("значимость").stress_options()) == {0, 1}


def issues(text: str, **spec) -> list[tuple[str, str]]:
    rep = scan(text, from_dict(spec))
    return [(i.severity, i.message) for i in rep.issues if i.code == "rhyme"]


HOMOGRAPHS_RU = (
    "Стоит на горке старый замок,\nГде тихо светится окно,\n"
    "Повесил я на дверь замок,\nХотя мне это всё равно.\n"
)
HOMOGRAPHS_EN = (
    "We walked for days across the desert,\nThe boats are sleeping in the bay,\n"
    "I swear that I will not desert,\nAnd sail with you so far away.\n"
)


@pytest.mark.parametrize("text, lang", [(HOMOGRAPHS_RU, "ru"), (HOMOGRAPHS_EN, "en")])
def test_homographs_stressed_apart_do_not_rhyme(text, lang):
    found = issues(text, language=lang, meter="iamb4", rhyme="ABAB")
    assert ("error", "rhyme A broken") in found
    assert not any("itself" in m for _, m in found)


@pytest.mark.parametrize(
    "text, lang, rhyme_",
    [
        ("Я жду тебя, и бьётся сердце,\nГде тихо светится окно,\n"
         "Нет места для чужого сердца,\nХотя мне это всё равно.\n", "ru", "ABAB"),
        ("Ու ես քեզ եմ տվել իմ սիրտս,\nՈւ ծաղիկներ կան մեր այգում,\n"
         "Ու դու ինձ ես տվել քո սիրտը,\nԵվ մի թռչուն է մեզ կանչում։\n", "hy", "ABAB"),
    ],
)  # fmt: skip
def test_a_word_rhymed_with_its_own_form_is_named(text, lang, rhyme_):
    found = issues(text, language=lang, rhyme=rhyme_, min_rhyme="slant")
    assert any(sev == "warning" and "form of the same word" in m for sev, m in found), found


def test_homophones_of_different_words_are_a_rhyme():
    text = "Я вышел утром в чистый луг,\nИ там я посадил свой лук.\n"
    found = issues(text, language="ru", rhyme="AA")
    assert found == []


def test_a_word_rhymed_with_itself_is_still_named():
    text = "Ты моя любовь,\nИ снова любовь.\n"
    found = issues(text, language="ru", rhyme="AA")
    assert any("with itself" in m for _, m in found)
