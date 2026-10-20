import pytest

from ashugh import lang, meter, rhyme
from ashugh.lang import en
from ashugh.scan import analyze_lines, scan
from ashugh.spec import Spec, from_dict


def word(token):
    return en.analyze_word(token)


@pytest.mark.parametrize(
    "token,size",
    [
        ("beautiful", 3),
        ("cat", 1),
        ("today", 2),
        ("understand", 3),
        ("summer's", 2),
        ("don't", 1),
        ("I'm", 1),
        ("lovin", 2),
    ],
)
def test_dictionary_syllables(token, size):
    assert word(token).size == size


@pytest.mark.parametrize(
    "token,stress",
    [("beautiful", 0), ("today", 1), ("understand", 2), ("forever", 1)],
)
def test_primary_stress(token, stress):
    assert word(token).stress_options() == [stress]


def test_secondary_stress_is_kept():
    w = word("understand")
    assert w.readings[0].secondary == (0,)


def test_function_words_are_clitics_and_content_monosyllables_are_free():
    assert word("the").clitic and word("of").clitic
    w = word("night")
    assert w.weak and not w.clitic


def test_variant_with_one_vowel_fewer_becomes_droppable():
    w = word("every")
    assert w.size == 3 and w.drop == 1
    words = lang.analyze("en", ["every", "day"], {})
    assert meter.fit(words, "free", count=3).count == 3
    assert meter.fit(words, "free", count=4).count == 4


def test_unknown_word_is_guessed_not_dropped():
    w = word("zorblaxian")
    assert w.guessed and w.size >= 3
    assert w.stress_options() == list(range(w.size))


@pytest.mark.parametrize("token", ["flz", "Xq"])
def test_vowelless_unknown_still_has_a_syllable(token):
    w = word(token)
    assert w.size == 1 and w.readings


@pytest.mark.parametrize(
    "token,n",
    [
        ("table", 2),
        ("make", 1),
        ("queue", 1),
        ("loved", 1),
        ("wanted", 2),
        ("happy", 2),
        ("smile", 1),
        ("people", 2),
    ],
)
def test_spelling_heuristic(token, n):
    assert en.guess_syllables(token) == n


def test_detects_iambic_pentameter():
    lines = analyze_lines(
        "Shall I compare thee to a summer's day?\nThou art more lovely and more temperate:",
        Spec(),
        "en",
    )
    assert meter.detect(lines) == "iamb"
    assert meter.fit(lines[0].words, "iamb").feet == 5


def test_detects_trochee():
    lines = analyze_lines("Tiger, tiger, burning bright,\nIn the forests of the night", Spec())
    assert lines[0].lang == "en"
    assert meter.detect(lines) == "trochee"


def tails(a, b):
    return [
        rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in analyze_lines(f"{a}\n{b}", Spec())
    ]


@pytest.mark.parametrize(
    "a,b,expected",
    [
        ("day", "away", "perfect"),
        ("bright", "night", "perfect"),
        ("heart", "start", "perfect"),
        ("fire", "desire", "perfect"),
        ("love", "move", "none"),
        ("cat", "dog", "none"),
    ],
)
def test_english_rhyme(a, b, expected):
    assert rhyme.level(rhyme.match(*tails(a, b))[0]) == expected


def test_latin_words_in_a_russian_line_are_english_now():
    rep = scan("Oh baby я жду тебя", from_dict({"syllables": 7}), lang="ru")
    assert rep.ok
    assert not [i for i in rep.issues if i.code == "script"]


def test_spec_accepts_english():
    assert from_dict({"language": "en"}).language == "en"


@pytest.mark.parametrize(
    "token,pieces",
    [
        ("beautiful", ["beau", "ti", "ful"]),
        ("understand", ["un", "der", "stand"]),
        ("summer's", ["sum", "mer's"]),
        ("today", ["to", "day"]),
        ("fire", ["fi", "re"]),
        ("happy", ["hap", "py"]),
    ],
)
def test_display_pieces(token, pieces):
    assert [s.text for s in word(token).syllables] == pieces


def test_pieces_always_match_the_syllable_count():
    for token in ["idea", "rhythm", "fire", "every", "queue", "zorblaxian", "flz"]:
        w = word(token)
        assert len(w.syllables) == w.size and all(s.text for s in w.syllables)


def test_lexicon_override_in_arpabet():
    w = en.analyze_word("zorblax", {"zorblax": "Z AO1 R B L AE0 K S"})
    assert not w.guessed and w.size == 2 and w.stress_options() == [0]


def test_lexicon_override_without_digits_is_ignored():
    w = en.analyze_word("zorblax", {"zorblax": "zor-blax"})
    assert w.guessed


@pytest.mark.parametrize(
    "word,n,parts",
    [
        ("between", 2, ["be", "tween"]),
        ("without", 2, ["wi", "thout"]),
        ("declines", 2, ["de", "clines"]),
        ("father", 2, ["fa", "ther"]),
        ("sometime", 2, ["some", "time"]),
        ("lovely", 2, ["love", "ly"]),
        ("careful", 2, ["care", "ful"]),
        ("little", 2, ["lit", "tle"]),
        ("candle", 2, ["can", "dle"]),
        ("table", 2, ["ta", "ble"]),
        ("summer", 2, ["sum", "mer"]),
        ("beautiful", 3, ["beau", "ti", "ful"]),
        ("complete", 2, ["com", "plete"]),
    ],
)
def test_spelling_split_for_display(word, n, parts):
    assert en.split_spelling(word, n) == parts


@pytest.mark.parametrize("word,n", [("strengths", 1), ("rhythm", 2), ("a", 1), ("fire", 2)])
def test_spelling_split_always_gives_n_pieces(word, n):
    pieces = en.split_spelling(word, n)
    assert len(pieces) == n and "".join(pieces).replace("-", "") in (word, word * 2)


@pytest.mark.parametrize("word,size", [("us", 1), ("ab", 1), ("mam", 1), ("every", 3), ("fire", 2)])
def test_spelled_out_abbreviations_are_not_readings(word, size):
    assert en.analyze_word(word).size == size


def test_droppable_syllables_survive():
    assert en.analyze_word("every").drop is not None
    assert en.analyze_word("fire").drop is not None
