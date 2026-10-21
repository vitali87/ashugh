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
    from ashugh import report

    out = report.text(check("Every day I'm struggling\n", syllables=6, meter="trochee"), True)
    assert "strug-gling" in out


def test_blessed_may_be_sung_in_two_syllables():
    text = (
        "Holy, holy, holy! Lord God Almighty!\nEarly in the morning our song shall rise to thee;\n"
        "Holy, holy, holy! merciful and mighty!\nGod in three Persons, blessed Trinity!\n"
    )
    assert errors(text, syllables=[11, 12, 12, 10]) == []


def test_blessed_is_one_syllable_by_default():
    report = check("We are blessed\n")
    assert report.lines[0].fit.count == 3


@pytest.mark.parametrize(
    "a,b",
    [("beer", "out 'ere"), ("apart", "my 'eart"), ("land", "in 'is 'and")],
)
def test_a_cockney_dropped_h_reads_as_the_word(a, b):
    assert en_rhyme(a, b) >= rhyme.THRESHOLD["perfect"]


def test_a_dropped_h_word_keeps_its_own_part_of_speech():
    hand = next(w for w in words("'Is 'and was cold") if w.text == "and")
    assert not hand.clitic


@pytest.mark.parametrize("line,norm", [("need 'em now", "em"), ("a good 'un", "un")])
def test_em_and_un_are_no_dropped_h(line, norm):
    w = next(w for w in words(line) if w.norm == norm)
    assert not w.readings[0].phones[:1] == ("h",)
    assert "ɛm" not in "".join(w.readings[0].phones) or norm == "em"


def test_kiplings_gunga_din_rhymes():
    text = (
        "You may talk o' gin and beer\nWhen you're quartered safe out 'ere,\n"
        "An' you're sent to penny-fights an' Aldershot it;\n"
        "But when it comes to slaughter\nYou will do your work on water,\n"
        "An' you'll lick the bloomin' boots of 'im that's got it.\n"
    )
    assert not any("rhyme" in m for m in errors(text, rhyme="AABCCB"))


@pytest.mark.parametrize("word", ["aspire", "admire", "inspire", "spire"])
def test_ire_words_have_the_long_reading_too(word):
    w = words(word)[0]
    assert w.drop is not None and w.drop_cost < 0  # short first, long when the line needs it


def test_blakes_tyger_derives_one_ending_for_a_rhyme_pair():
    text = (
        "In what distant deeps or skies.\nBurnt the fire of thine eyes?\n"
        "On what wings dare he aspire?\nWhat the hand, dare seize the fire?\n"
    )
    data = translate.derive_spec(check(text), keep={"syllables", "endings", "rhyme"})
    stanza = data["stanza"]["1"]
    assert stanza["syllables"][2] == stanza["syllables"][3]
    assert stanza["endings"][2] == stanza["endings"][3]


def test_a_zero_count_frees_a_line_of_its_feet_and_meter():
    text = (
        "[Verse]\nI walk along the river side\n\n"
        "[Spoken]\nAnd then she said to me that nothing ever really ends\n"
    )
    spec = from_dict(
        {
            "language": "en",
            "syllables": 8,
            "meter": "iamb4",
            "section": {"spoken": {"syllables": [0]}},
        }
    )
    report = scan(text, spec)
    spoken = report.lines[-1]
    assert spoken.ok, spoken.issues


def test_a_zero_count_still_leaves_the_other_lines_checked():
    text = "[Verse]\nI walk along the river side today\n\n[Spoken]\nAnd then she said\n"
    spec = from_dict(
        {
            "language": "en",
            "syllables": 8,
            "meter": "iamb4",
            "section": {"spoken": {"syllables": [0]}},
        }
    )
    assert not scan(text, spec).lines[0].ok


@pytest.mark.parametrize(
    "line,word", [("I'm the OG on the block", "OG"), ("a KO in the ring", "KO")]
)
def test_og_and_ko_are_letters(line, word):
    w = next(w for w in words(line) if w.text == word)
    assert w.size == 2 and w.spelled


def test_ok_is_still_a_word_of_two_syllables():
    assert words("I'm OK")[-1].size == 2


@pytest.mark.parametrize(
    "word,stressed",
    [
        ("o'erwhelms", 1),
        ("o'erthrown", 1),
        ("e'erlasting", 1),
        ("o'ercome", 1),
        ("ne'ertheless", 2),
    ],
)
def test_oer_compounds_are_known_and_stressed_after_oer(word, stressed):
    w = words(word)[0]
    assert not w.guessed
    assert w.readings[0].stress == stressed


@pytest.mark.parametrize("word,n", [("thro'", 1), ("gon'", 1), ("Fount", 1)])
def test_hymn_and_rap_spellings_are_known(word, n):
    w = words(f"We {word} away")[1]
    assert not w.guessed and w.size == n


@pytest.mark.parametrize("word,n", [("Aurelius", 4), ("Tarquinius", 4), ("Coriolanus", 5)])
def test_a_guessed_name_counts_its_hiatus(word, n):
    assert words(word)[0].size == n


@pytest.mark.parametrize("word,n", [("Ignatius", 3), ("Bianca", 3)])
def test_a_glide_after_t_is_no_hiatus(word, n):
    assert words(word)[0].size == n


def test_the_meter_error_quotes_the_slots_template():
    report = check("Eternal Father, strong to save\n", syllables=8, meter="dactyl3", endings="f")
    detail = next(i.detail for i in report.lines[0].issues if i.code == "meter")
    assert detail.endswith("dactyl3 wants /xx/xx/x")


@pytest.mark.parametrize("a,b", [("Graceland", "hand"), ("Neverland", "understand")])
def test_land_compounds_rhyme_on_land(a, b):
    assert en_rhyme(a, b) >= rhyme.THRESHOLD["perfect"]


@pytest.mark.parametrize("word", ["twinkling", "jingling", "trembling"])
def test_a_syllabic_l_word_is_two_syllables_in_free_verse(word):
    report = check(f"The {word} of the bells\n")
    assert report.lines[0].fit.count == 6


def test_poes_bells_count_as_spoken():
    report = check("From the jingling and the tinkling of the bells\n")
    assert report.lines[0].fit.count == 11


def test_a_syllabic_l_word_still_takes_three_where_the_meter_asks():
    report = check("The stars are twinkling bright tonight\n", syllables=9)
    assert report.ok
