"""Round 17 of dogfooding, English: what a songwriter found wrong."""

import pytest

from ashugh import meter, rhyme, suno, translate
from ashugh.lang import en
from ashugh.scan import analyze_lines, scan
from ashugh.spec import Spec, from_dict


def words(line: str):
    (ln,) = analyze_lines(line, Spec(language="en"))
    return ln.words


def en_rhyme(a: str, b: str) -> float:
    lines = analyze_lines(f"{a}\n{b}", Spec(language="en"))
    return rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))[0]


def check(text: str, **spec):
    return scan(text, from_dict({"language": "en", **spec}))


def errors(text: str, **spec) -> list[str]:
    return [
        i.message for lr in check(text, **spec).lines for i in lr.issues if i.severity == "error"
    ]


def split_all(text: str, **spec) -> str:
    return suno.format_song(
        text, from_dict({"language": "en", **spec}), split="all", tags=False
    ).text


@pytest.mark.parametrize(
    "word", ["struggling", "juggling", "troubling", "humbling", "beloved", "crumbling"]
)
def test_a_short_reading_keeps_the_words_stress(word):
    w = words(word)[0]
    assert w.drop is not None
    stress = w.readings[0].stress
    assert w.drop != stress, "the dropped vowel is never the stressed one"


def test_struggling_and_juggling_rhyme_when_sung_short():
    text = "Every day I'm struggling\nEvery night I'm juggling\n"
    assert errors(text, syllables=6, rhyme="AA", meter="trochee") == []


def test_beloved_rhymes_with_shoved():
    assert en_rhyme("beloved", "shoved") >= rhyme.THRESHOLD["perfect"]


def test_a_stressed_syllable_off_the_beat_after_a_short_reading_fails():
    assert any(
        "off the beat" in m
        for m in errors("The bells humbling ring now\n", syllables=6, meter="iamb3")
    )


@pytest.mark.parametrize(
    "line",
    ["And heaven and nature sing", "Which heaven to gaudy day denies"],
)
def test_heaven_may_be_sung_in_one_syllable(line):
    w = next(w for w in words(line) if w.norm == "heaven")
    assert w.drop == 1
    assert w.drop_cost > 0, "a licence, taken only when the line needs it"


def test_joy_to_the_world_passes_common_meter():
    text = (
        "Joy to the world! the Lord is come;\nLet earth receive her King;\n"
        "Let every heart prepare him room,\nAnd heaven and nature sing.\n"
    )
    assert errors(text, syllables=[8, 6, 8, 6], meter="iamb") == []


def test_heaven_keeps_two_syllables_where_the_line_has_room():
    report = check("The gates of heaven open wide\n", syllables=8, meter="iamb4")
    assert report.ok
    assert report.lines[0].fit.count == 8


@pytest.mark.parametrize(
    "word,short", [("heaven", "heav'n"), ("given", "giv'n"), ("heavens", "heav'ns")]
)
def test_the_short_heaven_is_written_heavn(word, short):
    pieces = en.split_spelling(word, 2)
    assert "".join(en.sung_pieces(pieces, 1, True)) == short


def test_a_two_syllable_word_without_a_v_before_its_n_keeps_both():
    assert words("garden")[0].drop is None
    assert words("open")[0].drop is None


def test_derived_endings_of_a_dactylic_rhyme_stay_dactylic():
    text = (
        "I'll love you for eternity\nOur hearts in pure fraternity\n"
        "The stars above in harmony\nAre singing songs of melody\n"
    )
    data = translate.derive_spec(check(text), keep={"syllables", "meter", "rhyme", "endings"})
    stanza = data["stanza"]["1"]
    assert stanza["endings"] == "dddd"
    spec = from_dict({"language": "en", **stanza})
    report = scan(text, spec)
    assert report.ok and not any(i.code == "spec" for lr in report.lines for i in lr.issues)


def test_hoods_triple_rhyme_derives_dactylic_endings():
    text = (
        "Take her up tenderly,\nLift her with care;\nFashion'd so slenderly,\nYoung, and so fair!\n"
    )
    data = translate.derive_spec(check(text), keep={"endings", "rhyme"})
    assert data["stanza"]["1"]["endings"] == "dmdm"


def test_an_unrhymed_y_line_keeps_its_own_ending():
    text = (
        "Row, row, row your boat,\nGently down the stream.\n"
        "Merrily, merrily, merrily, merrily,\nLife is but a dream.\n"
    )
    data = translate.derive_spec(check(text), keep={"endings"})
    assert data["stanza"]["1"]["endings"][2] == "d"


def test_melody_rhymed_with_free_still_ends_masculine():
    text = "We sing a simple melody\nTogether we are free\n"
    data = translate.derive_spec(check(text), keep={"endings", "rhyme"})
    assert data["stanza"]["1"]["endings"] == "mm"


def test_a_slot_its_own_lines_pass_is_no_impossible_slot():
    text = "I'll love you for eternity\nOur hearts in pure fraternity\n"
    report = check(text, syllables=8, meter="iamb3", endings="m", rhyme="AA")
    assert not any(i.code == "spec" for lr in report.lines for i in lr.issues)


def test_an_impossible_slot_no_line_passes_is_still_warned():
    report = check("The night is long and cold\n", syllables=9, meter="iamb3", endings="m")
    assert any(
        i.code == "spec" and "no line can pass" in i.detail
        for lr in report.lines
        for i in lr.issues
    )


@pytest.mark.parametrize(
    "word,n,pieces",
    [
        ("struggling", 3, ["strug", "gl", "ing"]),
        ("twinkling", 3, ["twin", "kl", "ing"]),
        ("trembling", 3, ["trem", "bl", "ing"]),
        ("chasm", 2, ["chas", "m"]),
        ("rhythm", 2, ["rhyth", "m"]),
        ("desiring", 4, ["de", "si", "r", "ing"]),
        ("voyage", 2, ["voy", "age"]),
        ("whereon", 2, ["where", "on"]),
        ("wherein", 2, ["where", "in"]),
        ("thereon", 2, ["there", "on"]),
        ("outrageous", 3, ["out", "ra", "geous"]),
    ],
)
def test_split_pieces_follow_the_sound(word, n, pieces):
    assert en.split_spelling(word, n) == pieces


@pytest.mark.parametrize(
    "word,n,pieces",
    [("outside", 2, ["out", "side"]), ("outer", 2, ["ou", "ter"]), ("little", 2, ["lit", "tle"])],
)
def test_split_pieces_that_were_right_stay(word, n, pieces):
    assert en.split_spelling(word, n) == pieces


@pytest.mark.parametrize(
    "line,piece",
    [
        ("The stars are twinkling bright", "twin-kling"),
        ("My heart is trembling now", "trem-bling"),
        ("The walls are crumbling down", "crum-bling"),
    ],
)
def test_suno_splits_a_short_syllabic_l_word_with_a_vowel_in_each_piece(line, piece):
    assert piece in split_all(line + "\n", syllables=6, meter="iamb3")


@pytest.mark.parametrize(
    "line,piece",
    [
        ("A chasm in the night", "chas-um"),
        ("The desiring heart", "de-si-er-ing"),
        ("So inspiring the voyage home", "voy-age"),
    ],
)
def test_suno_never_writes_a_piece_without_a_vowel(line, piece):
    out = split_all(line + "\n")
    assert piece in out
    for word in out.split():
        for p in word.strip(",.").split("-"):
            assert any(ch in "aeiouyAEIOUY" for ch in p) or "'" in p, out


def test_the_scan_shows_a_short_syllabic_l_word_as_sung():
    out = check("Every day I'm struggling\n", syllables=6, meter="trochee")
    note = next(i for i in out.lines[0].issues if "struggling" in i.message)
    assert "strug-gling" in note.detail or "strug-gling" in note.message
