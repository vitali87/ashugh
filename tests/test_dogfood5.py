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
