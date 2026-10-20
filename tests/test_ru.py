import pytest

from ashugh.lang import ru
from ashugh.lang.ru_lexicon import TABLE, StressTable


def stresses(word):
    return sorted(ru.analyze_word(word).stress_options())


def test_table_binary_search_hits_and_misses():
    assert TABLE.get("ещё") == (1,)
    assert TABLE.get("замок") == (0, 1)
    assert TABLE.get("ыыыы") is None
    assert TABLE.get("") is None


def test_table_edges():
    data = "аб\t1\nвг\t2\nяя\t12\n".encode()
    t = StressTable(data)
    assert t.get("аб") == (0,)
    assert t.get("яя") == (0, 1)
    assert t.get("вг") == (1,)
    assert t.get("бб") is None
    assert t.get("яяя") is None


@pytest.mark.parametrize(
    "word,expected",
    [
        ("дядя", [0]),
        ("заставил", [1]),
        ("занемог", [2]),
        ("правил", [0, 1]),
        ("замок", [0, 1]),
        ("еще", [1]),
        ("мгновенье", [1]),
        ("виденье", [0, 1]),
        ("мглою", [0]),
        ("него", [1]),
        ("кто-нибудь", [0]),
    ],
)
def test_stress(word, expected):
    assert stresses(word) == expected


def test_marks_override_the_table():
    assert stresses("замо́к") == [1]
    assert stresses("замОк") == [1]
    assert stresses("Замок") == [0, 1]  # a sentence capital is not a mark


def test_yo_is_restored():
    spellings = {r.spelling for r in ru.analyze_word("еще").readings}
    assert spellings == {"ещё"}
    spellings = {r.spelling for r in ru.analyze_word("все").readings}
    assert spellings == {"все", "всё"}


def test_unknown_word_offers_every_vowel():
    w = ru.analyze_word("зряченюхослышащий")
    assert w.guessed and len(w.stress_options()) == w.size


def test_consonant_only_prepositions_have_no_syllables():
    assert ru.analyze_word("в").size == 0
    assert ru.analyze_word("с").clitic


@pytest.mark.parametrize(
    "word,stress,sound",
    [
        ("сердце", 0, "sʲertsɨ"),
        ("солнце", 0, "sontsɨ"),
        ("честный", 0, "tʃʲesnɨj"),
        ("что", 0, "ʃto"),
        ("любовь", 1, "lʲubofʲ"),
        ("снег", 0, "snʲek"),
        ("его", 1, "jɪvo"),
        ("молоко", 2, "mələko"),
    ],
)
def test_transcription(word, stress, sound):
    assert "".join(ru.transcribe(word, stress)) == sound


@pytest.mark.parametrize(
    "word,parts",
    [
        ("морозы", ["мо", "ро", "зы"]),
        ("только", ["толь", "ко"]),
        ("семья", ["се", "мья"]),
        ("война", ["вой", "на"]),
        ("честных", ["чест", "ных"]),
        ("кто-то", ["кто", "то"]),
    ],
)
def test_display_syllables(word, parts):
    assert ru.split_syllables(word) == parts
