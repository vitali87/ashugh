"""Round 15 of dogfooding, English: what a songwriter found wrong."""

import pytest

from ashugh import meter, rhyme
from ashugh.scan import analyze_lines, scan
from ashugh.spec import Spec, from_dict


def words(line: str):
    (ln,) = analyze_lines(line, Spec(language="en"))
    return ln.words


def rhymes(a: str, b: str) -> float:
    lines = analyze_lines(f"{a}\n{b}", Spec(language="en"))
    return rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))[0]


@pytest.mark.parametrize(
    "text,spec",
    [
        ("Put on the record\nThe crowd adored\n", {"rhyme": "AA"}),
        ("Put on my record\nThe crowd adored\n", {"rhyme": "AA"}),
        ("We cross the desert\nForever alert\n", {"rhyme": "AA"}),
        ("I found a present\nThat I resent\n", {"rhyme": "AA"}),
    ],
)
def test_a_noun_after_a_determiner_cannot_buy_a_rhyme_with_the_verb_stress(text, spec):
    report = scan(text, from_dict({"language": "en", **spec}))
    assert any(i.code == "rhyme" and i.severity == "error" for i in report.issues)


@pytest.mark.parametrize("line", ["I want to record", "They will object", "we present"])
def test_a_verb_after_its_subject_keeps_the_verb_stress(line):
    assert words(line)[-1].readings[0].stress == 1


@pytest.mark.parametrize(
    "token,size",
    [
        ("whyyyy", 1), ("nooooo", 1), ("Babyyyy", 2), ("Yeahhhh", 1), ("Ooooh", 1), ("Aaah", 1),
        ("looove", 1), ("Yesss", 1), ("Loooong", 1), ("Heyyyy", 1), ("Mmmmm", 1), ("Sooooo", 1),
    ],
)  # fmt: skip
def test_an_elongated_word_is_its_word_held(token, size):
    w = words(token)[0]
    assert w.size == size and not w.guessed, [r.source for r in w.readings]
    assert "".join(s.text for s in w.syllables) == token


@pytest.mark.parametrize(
    "a,b", [("Tell me whyyyy", "sky"), ("Baby, nooooo", "so"), ("looove", "above")]
)
def test_an_elongated_word_rhymes_as_its_word(a, b):
    assert rhymes(a, b) >= 0.9


def test_a_sound_with_a_triple_letter_stays_itself():
    assert words("Brrr")[0].size == 1


@pytest.mark.parametrize(
    "text",
    [
        "We danced until the midnight\nUnder the silver light\n",
        "Sleep, little sparrow, goodnight\nStars on the water are bright\n",
    ],
)
def test_a_secondary_stress_rhyme_takes_its_ending_from_that_stress(text):
    from ashugh.translate import derive_spec

    data = derive_spec(scan(text), {"rhyme", "endings"})
    assert data["stanza"]["1"]["endings"] == "mm"
    report = scan(text, from_dict({"language": "en", "endings": "mm", "rhyme": "AA"}))
    assert report.ok, report.issues


def test_a_primary_ending_still_counts():
    report = scan("We danced until the midnight\n", from_dict({"language": "en", "endings": "f"}))
    assert report.ok, report.issues


@pytest.mark.parametrize(
    "token,size",
    [
        ("time'll", 2),
        ("love'll", 2),
        ("road'll", 2),
        ("girl'll", 2),
        ("Kate'd", 2),
        ("he'll", 1),
        ("she'd", 1),
        ("y'all'll", 2),
    ],
)
def test_a_clitic_after_a_consonant_adds_a_vowel(token, size):
    assert words(token)[0].size == size


@pytest.mark.parametrize(
    "token,size",
    [
        ("lov'd", 1), ("believ'd", 2), ("reliev'd", 2), ("hop'd", 1), ("lin'd", 1), ("clos'd", 1),
        ("chang'd", 1), ("dimm'd", 1), ("stopp'd", 1), ("pierc'd", 1),
    ],
)  # fmt: skip
def test_an_elided_past_is_the_ed_form_with_its_e_unsung(token, size):
    w = words(token)[0]
    assert w.size == size and not w.guessed


def test_belovd_is_beloved_in_two():
    w = words("belov'd")[0]
    assert w.size == 2 and w.readings[0].stress == 1


@pytest.mark.parametrize("token", ["ow'st", "grow'st", "know'st"])
def test_an_elided_second_person_is_one_syllable(token):
    w = words(token)[0]
    assert w.size == 1 and not w.guessed


def test_amazing_grace_rhymes_in_its_old_spelling():
    assert rhymes("And grace my fears reliev'd;", "The hour I first believ'd!") >= 0.9
    assert (
        rhymes(
            "Nor lose possession of that fair thou ow'st;",
            "When in eternal lines to time thou grow'st:",
        )
        >= 0.9
    )


@pytest.mark.parametrize(
    "a,b",
    [
        ("melody", "free"),
        ("Every night I am chasing a melody", "And the music is setting me free"),
        ("destiny", "be"),
        ("memory", "free"),
    ],
)
def test_a_final_y_two_after_the_stress_rhymes_in_any_meter(a, b):
    assert rhymes(a, b) >= 0.7


def test_a_dolnik_song_rhymes_melody_and_free():
    text = "Every night I am chasing a melody\nAnd the music is setting me free\n"
    report = scan(text, from_dict({"language": "en", "rhyme": "AA"}))
    assert not [i for i in report.issues if i.code == "rhyme" and i.severity == "error"]


def test_a_final_y_next_to_the_stress_does_not_rhyme_on_it():
    assert rhymes("happy", "free") < 0.45


def pieces(word: str) -> str:
    from ashugh.lang import en

    return "-".join(s.text for s in en.analyze_word(word).syllables)


@pytest.mark.parametrize(
    "word,split",
    [
        ("hundred", "hun-dred"), ("kindred", "kin-dred"), ("sacred", "sa-cred"),
        ("creation", "cre-a-tion"), ("situation", "sit-u-a-tion"), ("graduation", "grad-u-a-tion"),
        ("walkest", "walk-est"), ("blesseth", "bless-eth"), ("worketh", "work-eth"),
        ("everyone", "ev-ery-one"), ("dishonest", "dis-hon-est"), ("baguette", "ba-guette"),
        ("learned", "learn-ed"), ("nation", "na-tion"), ("forest", "for-est"),
    ],
)  # fmt: skip
def test_split_display_round_15(word, split):
    assert pieces(word) == split


def displays(word: str) -> tuple[str, str, str]:
    from ashugh.lang import en

    w = en.analyze_word(word)
    pieces = [s.text for s in w.syllables]
    full = "-".join(en.sung_pieces(pieces, w.drop, False))
    short = "-".join(en.sung_pieces(pieces, w.drop, True))
    return full, short, w.sung(dropped=True)


@pytest.mark.parametrize(
    "word,full,short",
    [
        ("ourselves", "ou-er-selves", "our-selves"), ("hours", "hou-ers", "hours"),
        ("tired", "ti-erd", "tired"), ("desired", "de-si-erd", "de-sired"),
        ("fires", "fi-ers", "fires"), ("hourglass", "hou-er-glass", "hour-glass"),
        ("firelight", "fi-er-light", "fire-light"), ("fireside", "fi-er-side", "fire-side"),
        ("fire", "fi-er", "fire"), ("flower", "flow-er", "flower"),
    ],
)  # fmt: skip
def test_a_hidden_er_is_sung_as_er_anywhere_in_the_word(word, full, short):
    got = displays(word)
    assert got[:2] == (full, short)
    assert got[2] == short  # syl runs it into the syllable before


def test_a_vowel_dropped_before_r_goes_with_the_r():
    assert displays("every")[2] == "ev-ery"
    assert displays("every")[1] == "ev'-ry"


def test_a_compound_with_a_droppable_part_keeps_its_drop():
    from ashugh.lang import en

    assert en.analyze_word("firelight").drop == 1  # fire: one syllable or two
    assert en.analyze_word("lovestruck").drop is None


@pytest.mark.parametrize(
    "word,split",
    [
        ("language", "lan-guage"), ("liquid", "li-quid"), ("penguin", "pen-guin"),
        ("anyone", "an-y-one"), ("everybody", "ev-ery-bod-y"), ("harvest", "har-vest"),
        ("latest", "la-test"), ("interest", "in-te-rest"), ("chocolate", "cho-co-late"),
        ("cooperation", "co-op-e-ra-tion"), ("association", "as-so-ci-a-tion"),
    ],
)  # fmt: skip
def test_split_display_negatives_and_neighbours(word, split):
    assert pieces(word) == split


def test_a_partner_ending_in_a_leaning_pronoun_is_asked_for_as_the_line_sings_it():
    from ashugh.fit import requests_for

    text = "My heart is broke in two\nI need a brand new tune\nI think I'm over you\n"
    reqs = {r.id: r for r in requests_for(text, from_dict({"language": "en", "rhyme": "AAA"}))}
    assert reqs["L1"].ending == "masculine"
    assert reqs["L1"].rhyme_with == ["you"] and reqs["L1"].rhyme_sound == "u"
    assert "over you" not in reqs["L2"].rhyme_with


def test_a_partner_with_one_reading_is_asked_for_as_before():
    from ashugh.fit import requests_for

    text = "My heart is broke in two\nI need a brand new tune\n"
    reqs = {r.id: r for r in requests_for(text, from_dict({"language": "en", "rhyme": "AA"}))}
    assert reqs["L2"].rhyme_with == ["two"] and reqs["L2"].ending == "masculine"


def test_a_capitalized_word_read_as_two_dictionary_words_is_named():
    text = "Persephone in the underworld\nAnd Eurydice\n"
    report = scan(text, from_dict({"language": "en"}))
    said = [i for i in report.issues if "read as" in i.message]
    assert [i.message for i in said] == [
        "«Persephone» read as perse + phone",
        "«Eurydice» read as eury + dice",
    ]
    assert "lexicon" in said[0].detail and said[0].data["parts"] == ["perse", "phone"]


def test_a_lowercase_compound_or_a_known_name_draws_no_such_warning():
    text = "So lovestruck in the moonlight\nPenelope and Hermione\n"
    report = scan(text, from_dict({"language": "en"}))
    assert not [i for i in report.issues if "read as" in i.message]


def test_a_lexicon_entry_silences_the_name_warning():
    spec = from_dict({"language": "en", "lexicon": {"persephone": "P ER0 S EH1 F AH0 N IY0"}})
    report = scan("Persephone in the underworld\n", spec)
    assert not [i for i in report.issues if "read as" in i.message]
    assert report.lines[0].line.words[0].size == 4


@pytest.mark.parametrize(
    "word,split",
    [
        ("hermione", "her-mi-o-ne"), ("calliope", "cal-li-o-pe"),
        ("science", "sci-ence"), ("violence", "vi-o-lence"),
    ],
)  # fmt: skip
def test_a_name_with_a_hiatus_and_a_sung_final_e_splits_at_both(word, split):
    assert pieces(word) == split


def test_a_dictionary_compound_at_a_line_start_draws_no_name_warning():
    report = scan(
        "Somewhere in the moonlight\nMoonlight on the barefoot\n", from_dict({"language": "en"})
    )
    assert not [i for i in report.issues if "read as" in i.message]
