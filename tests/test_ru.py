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


@pytest.mark.parametrize(
    "word,expected",
    [
        ("буду", [0]),
        ("будешь", [0]),
        ("будут", [0]),
        ("нашу", [0]),
        ("одном", [1]),
        ("теряя", [1]),
        ("зная", [0]),
        ("мечтая", [1]),
        ("дыша", [1]),
        ("видя", [0]),
        ("томясь", [1]),
        ("касаясь", [1]),
        ("начав", [1]),
        ("вспомнив", [0]),
        ("упав", [1]),
        ("забыв", [1]),
        ("создавший", [1]),
        ("враждующих", [1]),
        ("звучал", [1]),
        ("звучали", [1]),
        ("свалилась", [1]),
        ("краю", [0, 1]),
    ],
)
def test_forms_the_dictionary_lacks(word, expected):
    w = ru.analyze_word(word)
    assert not w.guessed
    assert sorted(w.stress_options()) == expected


def test_a_real_unknown_word_is_still_guessed():
    assert ru.analyze_word("кракозябрами").guessed


def test_unknown_words_get_a_suffix_prior():
    w = ru.analyze_word("зюзюкация")  # -ация is stressed on its а: информа́ция
    assert w.guessed
    first = w.readings[0]
    assert first.stress == 2 and first.penalty == 0
    assert all(r.penalty > 0 for r in w.readings[1:])


def test_suffix_prior_is_a_preference_not_a_rule():
    from ashugh import meter

    w = ru.analyze_word("зюзюкация")
    assert meter.fit([w], "free").stresses[0] == 2
    assert meter.fit([w], "trochee").stresses[0] in (0, 2)
    assert meter.fit([w], "dactyl").stresses[0] == 0  # the meter can still overrule it


def test_suffix_table_lookup():
    assert ru.suffix_prior("информация") == 2
    assert ru.suffix_prior("ы") is None
    assert ru.analyze_word("кракозябрами").readings[0].penalty == 0
