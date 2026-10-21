"""Round 13 of dogfooding, English: what a songwriter found wrong."""

import pytest

from ashugh import suno
from ashugh.lang import en
from ashugh.scan import analyze_lines, scan
from ashugh.spec import Spec, from_dict


def words(text: str) -> list:
    (ln,) = analyze_lines(text, Spec(language="en"))
    return ln.words


@pytest.mark.parametrize("token, sung", [("FYI", "F-Y-I"), ("AKA", "A-K-A")])
def test_an_abbreviation_the_dictionary_spells_or_expands_is_sung_letter_by_letter(token, sung):
    (w,) = words(f"{token}\n")
    assert w.spelled and w.size == 3 and w.sung().replace("(", "").startswith(sung[:1])
    assert "-".join(s.text for s in w.syllables) == sung


def test_a_lowercase_abbreviation_with_more_syllables_than_letters_is_not_garbled():
    (w,) = words("etc\n")
    assert w.size == 4 and "-".join(s.text for s in w.syllables) != "e-t-c-e"


def split(line: str) -> str:
    return suno.format_song(line + "\n", tags=False, split="all").text.strip()


def test_suno_writes_a_spelled_abbreviation_as_its_letters():
    assert split("WTF") == "W-T-F"
    assert split("I got a W tonight") == "I got a W to-night"


def test_w_with_a_slash_is_with():
    (_, w, _) = words("me w/ you\n")
    assert w.size == 1


@pytest.mark.parametrize(
    "word, pieces",
    [
        ("science", "sci-ence"),
        ("violence", "vi-o-lence"),
        ("audience", "aud-i-ence"),
        ("seeing", "see-ing"),
        ("doing", "do-ing"),
        ("playing", "play-ing"),
        ("magician", "ma-gi-cian"),
        ("musician", "mu-si-cian"),
        ("orange", "or-ange"),
        ("forest", "for-est"),
        ("story", "sto-ry"),
        ("nation", "na-tion"),
        ("passion", "pas-sion"),
    ],
)
def test_written_words_are_cut_where_they_are_sung(word, pieces):
    assert "-".join(s.text for s in en.analyze_word(word).syllables) == pieces


@pytest.mark.parametrize(
    "line, out",
    [
        ("Come on baby light my fire", "fi-er"),
        ("We will dance until the hour", "hou-er"),
        ("I feel the power of desire", "de-si-er"),
    ],
)
def test_suno_writes_a_long_sung_ire_or_our_as_it_sounds(line, out):
    spec = from_dict({"language": "en", "syllables": len(line.split()) + 2})
    got = suno.format_song(line + "\n", spec=spec, tags=False, split="last").text
    assert got.split()[-1] == out


def test_suno_marks_a_dropped_vowel_with_an_apostrophe():
    spec = from_dict({"language": "en", "syllables": 4})
    got = suno.format_song("every day I wait\n", spec=spec, tags=False, split="all").text
    assert got.split()[0] == "ev'-ry"


GROUP = (
    "[Verse 1]\nMy daddy ran the feed store down\nBeside the old county line\n"
    "He hollered y'all come back around\nWe close up shop at ten\n"
)


def test_a_partner_rhymes_with_a_line_that_has_no_fix_as_it_is_written():
    from ashugh.fit import fit_song
    from ashugh.proposers import StaticProposer

    spec = from_dict({"language": "en", "syllables": [8, 6], "meter": "iamb", "rhyme": "ABAB"})
    res = fit_song(GROUP, spec, StaticProposer({5: ["We close up shop at nine"]}), rounds=1)
    assert [c.line for c in res.changes] == [5]
    assert res.text.splitlines()[4] == "We close up shop at nine"
    assert [u.line for u in res.unresolved] == [3]


@pytest.mark.parametrize("line", ["put a ring on it", "I'm on it", "look at it"])
def test_a_preposition_before_a_final_it_takes_the_stress(line):
    rep = scan(line + "\n", from_dict({"language": "en"}))
    assert rep.lines[0].fit.grid[-2:] == "/x"  # ón it


@pytest.mark.parametrize(
    "a, b", [("I'm on it", "you're on it"), ("put a ring on it", "go on and on it")]
)
def test_lines_ending_on_a_preposition_and_it_rhyme_on_the_preposition(a, b):
    from ashugh import meter, rhyme

    lines = analyze_lines(f"{a}\n{b}", Spec(language="en"))
    tails = [rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines]
    assert rhyme.match(*tails)[0] >= rhyme.THRESHOLD["near"]


def test_a_final_me_after_a_preposition_may_still_take_the_beat():
    rep = scan("come with me\n", from_dict({"language": "en", "meter": "trochee2"}))
    assert rep.ok


def test_a_ternary_slot_one_short_foot_long_is_no_impossible_slot():
    spec = {"language": "en", "meter": "anapest4", "syllables": 12, "endings": "f"}
    rep = scan("The master of method, the marvel of measure\n", from_dict(spec))
    assert rep.ok and not [i for i in rep.issues if "no line can pass" in i.detail]


def test_a_ternary_slot_far_too_short_is_still_impossible():
    spec = {"language": "en", "meter": "anapest4", "syllables": 8, "endings": "f"}
    rep = scan("The master of method\n", from_dict(spec))
    assert [i for i in rep.issues if "no line can pass" in i.detail]


@pytest.mark.parametrize(
    "line, word, stress",
    [
        ("put my record on the radio", "record", 0),
        ("I record the radio", "record", 1),
        ("baby you look perfect tonight", "perfect", 0),
        ("I want to perfect my art", "perfect", 1),
        ("the subject of my song", "subject", 0),
        ("I will present the case", "present", 1),
        ("a present for you", "present", 0),
        ("we protest all night", "protest", 1),
        ("it was an insult to me", "insult", 0),
        ("don't insult me", "insult", 1),
    ],
)
def test_a_noun_verb_pair_is_read_by_the_word_before_it(line, word, stress):
    ws = words(line + "\n")
    w = next(w for w in ws if w.norm == word)
    assert w.readings[0].stress == stress and w.readings[0].penalty == 0


BRIDGE = (
    "[Bridge]\nI'm fixin' to pack my bags and go\nDown to Tennessee\n"
    "Ain't nobody gonna know\nWhat become of me\n"
)


def test_a_derived_ending_follows_the_rhyme_the_line_makes():
    from ashugh.spec import dumps, loads
    from ashugh.translate import derive_spec

    src = scan(BRIDGE, from_dict({"language": "en"}))
    data = derive_spec(src, {"syllables", "meter", "rhyme", "endings"})
    assert data["stanza"]["1"]["endings"][3] == "m"  # rhymes on me, with Tennessee
    rep = scan(BRIDGE, loads(dumps({"language": "en", **data})))
    assert not [i for i in rep.issues if i.severity == "error"]
