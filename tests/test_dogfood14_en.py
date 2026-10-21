"""Round 14 of dogfooding, English: what a songwriter found wrong."""

import pytest

from ashugh import meter, rhyme
from ashugh.scan import analyze_lines, scan
from ashugh.spec import Spec, from_dict


def rhymes(a: str, b: str) -> float:
    lines = analyze_lines(f"{a}\n{b}", Spec(language="en"))
    return rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))[0]


@pytest.mark.parametrize(
    "a, b",
    [
        ("holy fire", "sky"),
        ("desire", "high"),
        ("higher", "sky"),
        ("hour", "now"),
        ("power", "cow"),
    ],
)
def test_a_word_sung_short_keeps_its_r(a, b):
    assert rhymes(a, b) < rhyme.THRESHOLD["near"]


@pytest.mark.parametrize("a, b", [("tired", "tide"), ("every", "heavy")])
def test_an_r_more_or_less_is_no_perfect_rhyme(a, b):
    assert rhymes(a, b) < rhyme.THRESHOLD["perfect"]


@pytest.mark.parametrize(
    "a, b", [("fire", "retire"), ("fire", "higher"), ("hour", "sour"), ("tired", "admired")]
)
def test_r_words_still_rhyme_with_each_other(a, b):
    assert rhymes(a, b) >= rhyme.THRESHOLD["near"]


def test_fire_and_sky_fail_a_rhyme_scheme():
    rep = scan(
        "I saw the light of holy fire\nAnd watched it rising to the sky\n",
        from_dict({"language": "en", "rhyme": "AA", "meter": "iamb4"}),
    )
    assert not rep.ok


FIRE = (
    "[V]\nI saw the glory of the fire\nAnd all my heart was free\n"
    "I heard the music of the choir\nIt sang of you and me\n"
)


def test_a_song_passes_the_spec_derived_from_it():
    from ashugh.spec import dumps, loads
    from ashugh.translate import derive_spec

    src = scan(FIRE, from_dict({"language": "en"}))
    data = derive_spec(src, {"syllables", "meter", "rhyme", "endings"})
    rep = scan(FIRE, loads(dumps({"language": "en", **data})))
    assert not [i.message for i in rep.issues if i.severity == "error"]


def en_word(token: str):
    from ashugh.lang import en

    return en.analyze_word(token)


@pytest.mark.parametrize(
    "token, size", [("mornin's", 2), ("warnin's", 2), ("evenin's", 2), ("somethin's", 2)]
)
def test_a_dropped_g_plural_is_the_ing_plural(token, size):
    w = en_word(token)
    assert w.size == size and not w.guessed


def test_dropped_g_plurals_rhyme():
    assert rhymes("Holdin' on to Sunday mornin's", "Y'all can keep your city warnin's") >= 0.7


def test_evenins_is_stressed_on_its_first_syllable():
    assert en_word("evenin's").readings[0].stress == 0


@pytest.mark.parametrize(
    "token, size",
    [
        ("pow'r", 1),
        ("flow'r", 1),
        ("heav'n", 1),
        ("pray'r", 1),
        ("ev'ry", 2),
        ("wand'ring", 2),
        ("pow'rful", 2),
        ("fall'n", 1),
        ("hist'ry", 2),
        ("fam'ly", 2),
    ],
)
def test_a_vowel_elided_with_an_apostrophe_is_known(token, size):
    w = en_word(token)
    assert w.size == size and not w.guessed


@pytest.mark.parametrize("a, b", [("pow'r", "hour"), ("heav'n", "leav'n"), ("o'er", "more")])
def test_elided_words_rhyme_as_they_sound(a, b):
    assert rhymes(a, b) >= rhyme.THRESHOLD["near"]


@pytest.mark.parametrize("token", ["don't", "we'll", "y'all", "ma'am", "o'clock"])
def test_contractions_are_read_as_the_dictionary_lists_them(token):
    from ashugh.lang import en

    listed = en.TABLE.get(token)
    assert listed is not None and en.lookup(token) == listed.split("|")


@pytest.mark.parametrize("token", ["liberty", "poverty", "tenderly", "property", "bitterly"])
def test_no_syncope_with_a_consonant_between_er_and_y(token):
    assert en_word(token).drop is None


@pytest.mark.parametrize("token", ["memory", "mystery", "every"])
def test_mem_ry_syncope_stays(token):
    assert en_word(token).drop is not None


def test_liberty_does_not_fit_five():
    rep = scan("[V]\nWe sang of liberty\n", from_dict({"language": "en", "syllables": 5}))
    assert not rep.ok


@pytest.mark.parametrize("line, size", [("Ba-da-ba-ba-ba, ba-da-ba-ba-ba", 10), ("Ba ba ba", 3)])
def test_a_capitalized_vocable_is_no_abbreviation(line, size):
    (ln,) = analyze_lines(line, Spec(language="en"))
    assert sum(w.size for w in ln.words) == size


def test_a_vocable_in_capitals_is_still_letters():
    (ln,) = analyze_lines("We met at the BA", Spec(language="en"))
    assert ln.words[-1].spelled


@pytest.mark.parametrize("token", ["NYC's", "MVP's"])
def test_a_possessive_abbreviation_is_spelt(token):
    w = en_word(token)
    assert w.spelled and w.size == 3 and w.syllables[-1].text.endswith("'s")


@pytest.mark.parametrize(
    "token, size, stress",
    [
        ("loveliness", 3, 0),
        ("homeliness", 3, 0),
        ("timelessly", 3, 0),
        ("gracelessly", 3, 0),
        ("wakefulness", 3, 0),
    ],
)
def test_a_suffix_after_a_silent_e_stem_adds_only_its_own_syllable(token, size, stress):
    w = en_word(token)
    assert (w.size, w.readings[0].stress) == (size, stress) and not w.guessed


def test_loveliness_fits_an_iamb_of_eight():
    rep = scan(
        "[V]\nI sing of all your loveliness\n",
        from_dict({"language": "en", "syllables": 8, "meter": "iamb4"}),
    )
    assert rep.ok, [i.message for i in rep.issues]


@pytest.mark.parametrize("token, size", [("y'all'd've", 2), ("y'all'd", 1), ("y'all'll", 2)])
def test_stacked_contractions_on_yall(token, size):
    w = en_word(token)
    assert w.size == size and not w.guessed


@pytest.mark.parametrize(
    "line",
    [
        "I bought the fifteen chairs",
        "I bought the sixteen chairs",
        "I bought the eighteen chairs",
        "I bought the thirteen chairs",
        "I bought an antique chair",
        "We ate the Chinese food",
    ],
)
def test_the_rhythm_rule_moves_a_late_stress_before_a_stressed_word(line):
    report = scan(line + "\n", from_dict({"language": "en", "meter": "iamb", "feet": 3}))
    assert report.lines[0].ok, report.lines[0].issues


@pytest.mark.parametrize("line", ["I counted to fifteen", "I found it so antique"])
def test_the_late_stress_stays_at_the_end_of_a_line(line):
    report = scan(line + "\n", from_dict({"language": "en", "meter": "iamb", "feet": 3}))
    assert report.lines[0].ok, report.lines[0].issues


@pytest.mark.parametrize("word", ["machine", "police", "believe"])
def test_a_reduced_pretonic_vowel_never_takes_the_clash(word):
    (ln,) = analyze_lines(word, Spec(language="en"))
    assert all(r.source != "clash" for r in ln.words[0].readings)


@pytest.mark.parametrize(
    "british,american",
    [
        ("organised", "organized"),
        ("memorised", "memorized"),
        ("criticised", "criticized"),
        ("harmonised", "harmonized"),
        ("analyse", "analyze"),
        ("colourful", "colorful"),
        ("favourite", "favorite"),
        ("neighbours", "neighbors"),
        ("litre", "liter"),
        ("sombre", "somber"),
        ("calibre", "caliber"),
        ("theatre", "theater"),
        ("centred", "centered"),
        ("manoeuvre", "maneuver"),
        ("jewellery", "jewelry"),
        ("travelled", "traveled"),
        ("travelling", "traveling"),
        ("catalogue", "catalog"),
        ("defence", "defense"),
        ("anaemia", "anemia"),
    ],
)
def test_a_british_spelling_reads_as_the_american(british, american):
    b, a = en_word(british), en_word(american)
    assert not b.guessed
    assert b.size == a.size
    assert b.readings[0].stress == a.readings[0].stress
    assert b.readings[0].phones == a.readings[0].phones


def test_british_spellings_rhyme_as_the_american():
    assert rhymes("harmonised", "surprised") >= 0.9
    assert rhymes("litre", "sweeter") >= 0.9


def test_a_line_with_british_spellings_counts_right():
    (ln,) = analyze_lines("A litre of sombre wine", Spec(language="en"))
    assert sum(w.size for w in ln.words) == 7


@pytest.mark.parametrize("word", ["four", "your", "acre", "promise", "otherwise", "tour"])
def test_listed_words_are_not_respelled(word):
    w = en_word(word)
    assert not w.guessed and all(r.source != "guess" for r in w.readings)


@pytest.mark.parametrize("word", ["goest", "doeth", "goers", "shoed"])
def test_an_archaic_or_inflected_oe_is_not_british(word):
    from ashugh.lang import en

    assert en.american(word) == []


def pieces(word: str) -> str:
    from ashugh.lang import en

    return "-".join(s.text for s in en.analyze_word(word).syllables)


@pytest.mark.parametrize(
    "word,split",
    [
        ("catalogue", "cat-a-logue"),
        ("dialogue", "di-a-logue"),
        ("fatigue", "fa-tigue"),
        ("colleagues", "col-leagues"),
        ("intrigue", "in-trigue"),
        ("unique", "u-nique"),
        ("argue", "ar-gue"),  # a sung ue stays
        ("choreographed", "cho-re-o-graphed"),
        ("triumphed", "tri-umphed"),
        ("theatre", "the-a-tre"),
        ("litre", "li-tre"),
        ("sombre", "som-bre"),
        ("darkness", "dark-ness"),
        ("weakness", "weak-ness"),
        ("sickness", "sick-ness"),
        ("blackness", "black-ness"),
        ("unknown", "un-known"),
        ("evermore", "ev-er-more"),
        ("nevermore", "nev-er-more"),
        ("riverside", "riv-er-side"),
        ("seventeen", "sev-en-teen"),
        ("uphill", "up-hill"),
        ("hothouse", "hot-house"),
        ("pothole", "pot-hole"),
        ("doghouse", "dog-house"),
        ("mishap", "mis-hap"),
        ("shepherd", "shep-herd"),
        ("haphazard", "hap-haz-ard"),
        ("uphold", "up-hold"),
        ("mother", "moth-er"),  # a true digraph stays whole
        ("bishop", "bish-op"),
        ("orphan", "or-phan"),
    ],
)
def test_split_spelling_cuts_where_the_word_is_said(word, split):
    assert pieces(word) == split


def test_suno_split_all_cuts_darkness_and_uphill_right():
    from ashugh import suno

    out = suno.format_song("The darkness and the weakness uphill\n", split="all", tags=False)
    assert "dark-ness" in out.text and "weak-ness" in out.text and "up-hill" in out.text


@pytest.mark.parametrize(
    "word,split",
    [
        ("apply", "ap-ply"),
        ("supply", "sup-ply"),
        ("reply", "re-ply"),
        ("assembly", "as-sem-bly"),
        ("humbly", "hum-bly"),
        ("simply", "sim-ply"),
        ("quickly", "quick-ly"),
        ("deeply", "deep-ly"),
        ("helpless", "help-less"),
        ("hopeless", "hope-less"),
        ("Italy", "It-a-ly"),
    ],
)
def test_ly_is_a_suffix_only_where_it_is_one(word, split):
    assert pieces(word) == split


@pytest.mark.parametrize(
    "word,split",
    [
        ("T-shirt", "T-shirt"),
        ("X-ray", "X-ray"),
        ("a-goin'", "a-go-in'"),
        ("hurricane's", "hur-ri-cane's"),
        ("LinkedIn", "Linked-In"),
        ("YouTube", "You-Tube"),
        ("PlayStation", "Play-Sta-tion"),
        ("rock-'n'-roll", "rock-'n'-roll"),
    ],
)
def test_split_spelling_cuts_at_hyphens_and_capitals(word, split):
    assert pieces(word) == split


@pytest.mark.parametrize(
    "word,n,split",
    [("learned", 2, "learn-ed"), ("blessed", 2, "bles-sed"), ("belovèd", 3, "be-lov-èd")],
)
def test_a_sung_ed_after_a_vowel_pair_is_its_own_piece(word, n, split):
    from ashugh.lang import en

    assert "-".join(en.split_spelling(word, n)) == split


@pytest.mark.parametrize(
    "line",
    [
        "do not desert",
        "I'll record",
        "they'll object",
        "shouldn't object",
        "we'd protest",
        "you won't rebel",
    ],
)
def test_a_heteronym_after_an_auxiliary_is_the_verb(line):
    (ln,) = analyze_lines(line, Spec(language="en"))
    assert ln.words[-1].readings[0].stress == 1


@pytest.mark.parametrize("line", ["it is not perfect", "it isn't present", "that's not content"])
def test_a_heteronym_after_be_not_stays_the_adjective(line):
    (ln,) = analyze_lines(line, Spec(language="en"))
    assert ln.words[-1].readings[0].stress == 0


def test_o_apostrophe_is_of_unstressed():
    from ashugh import lyrics

    assert lyrics.tokenize("a cup o' tea") == ["a", "cup", "o'", "tea"]
    (ln,) = analyze_lines("a cup o' tea", Spec(language="en"))
    o = ln.words[2]
    assert o.clitic and o.text == "o'"
    report = scan(
        "I'll have a cup o' tea\n", from_dict({"language": "en", "meter": "iamb", "feet": 3})
    )
    assert report.lines[0].ok, report.lines[0].issues


def test_o_apostrophe_does_not_swallow_other_quotes():
    from ashugh import lyrics

    assert lyrics.tokenize("the radio' plays") == ["the", "radio", "plays"]
    assert lyrics.tokenize("'O' is a letter") == ["O", "is", "a", "letter"]


@pytest.mark.parametrize(
    "line,size", [("AT&T", 4), ("R&B", 3), ("P&G", 3), ("rock & roll", 3), ("AT & T", 3)]
)
def test_capitals_glued_to_an_ampersand_are_letters(line, size):
    (ln,) = analyze_lines(line, Spec(language="en"))
    assert sum(w.size for w in ln.words) == size


@pytest.mark.parametrize("sep", ["\n", "\r", " ", " ", "\x0b", "\x0c", "\x85"])
def test_a_candidate_with_any_line_break_is_more_than_one_line(sep):
    from ashugh import fit

    assert fit._clean(f"I walk along the river{sep}side") == "more than one line"


def test_candidates_for_a_repeated_line_are_used_and_not_called_passing():
    from ashugh.fit import fit_song
    from ashugh.proposers import StaticProposer

    line = "We sing all through the long dark night\n"
    text = "[Chorus]\n" + line + line
    spec = from_dict({"language": "en", "syllables": 6})
    proposer = StaticProposer({3: ["We sing the whole night through"]})
    result = fit_song(text, spec, proposer, rounds=1)
    assert result.text.count("We sing the whole night through") == 2
    assert proposer.unused({2, 3}) == []


def test_forbid_final_takes_a_comma_list_like_syllables(tmp_path, capsys):
    from ashugh.cli import main

    song = tmp_path / "s.txt"
    song.write_text("I keep on running\nAnd I keep on jumpin'\n", encoding="utf-8")
    main(["scan", str(song), "--forbid-final", "ing,in'", "--json"])
    import json

    data = json.loads(capsys.readouterr().out)
    finals = [i for i in data["issues"] if i["code"] == "final"]
    assert {i["line"] for i in finals} == {1, 2}


def test_an_off_beat_word_is_quoted_as_the_line_sings_it():
    limerick = (
        "[Verse]\nA baker who lived by the bay\nMade muffins and scones every day;\n"
        "When the oven caught fire,\nHe just climbed a bit higher,\n"
        "And frosted the flames anyway.\n"
    )
    report = scan(limerick, from_dict({"language": "en", "meter": "anapest"}))
    (beat,) = [i for i in report.issues if "off the beat" in i.message]
    assert "e\u0301ve-ry" in beat.message and "-e-ry" not in beat.message


@pytest.mark.parametrize(
    "word",
    [
        "glorious", "whispering", "wondering", "glittering", "flickering", "opening",
        "heavenly", "prettiest", "various", "heavier", "dangerous", "personal",
    ],
)  # fmt: skip
def test_a_post_tonic_weak_vowel_may_be_sung_away(word):
    from ashugh.lang import en

    w = en.analyze_word(word)
    assert w.drop is not None and w.drop_cost > 0  # a licence, taken when the line needs it


@pytest.mark.parametrize("word", ["liberty", "radio", "being", "poetry", "tenderly"])
def test_no_syncope_without_two_weak_vowels_side_by_side(word):
    from ashugh.lang import en

    assert en.analyze_word(word).drop is None


def test_a_hymn_sings_glorious_in_two():
    spec = from_dict({"language": "en", "syllables": 6, "meter": "iamb"})
    report = scan("Thy glorious name we sing\n", spec)
    assert report.lines[0].ok, report.lines[0].issues
    report = scan("We sang of liberty\n", from_dict({"language": "en", "syllables": 5}))
    assert not report.lines[0].ok


@pytest.mark.parametrize(
    "pieces,drop,sung",
    [
        (["glo", "ri", "ous"], 1, ["glo", "rious"]),
        (["pret", "ti", "est"], 1, ["pret", "tiest"]),
        (["whis", "per", "ing"], 1, ["whisp'", "ring"]),
        (["ev", "e", "ry"], 1, ["ev'", "ry"]),
    ],
)
def test_suno_sings_a_glide_into_the_next_vowel(pieces, drop, sung):
    from ashugh.lang import en

    assert en.sung_pieces(pieces, drop, True) == sung


def test_a_line_ending_in_digits_is_left_out_of_its_rhyme():
    text = "I was born in '99,\nAnd I like to walk the line\n"
    report = scan(text, from_dict({"language": "en", "rhyme": "AA"}))
    assert not [i for i in report.issues if i.code == "rhyme"]
    assert any("digits" in i.message for i in report.issues)


def test_a_digit_inside_the_line_keeps_its_rhyme():
    text = "Call me at 5 tonight\nAnd hold the morning light\n"
    report = scan(text, from_dict({"language": "en", "rhyme": "AA"}))
    assert [lr.letter for lr in report.lines] == ["A", "A"]
    assert not [i for i in report.issues if i.code == "rhyme"]
    text = "Call me at 5 tonight\nAnd hold the morning sun\n"
    report = scan(text, from_dict({"language": "en", "rhyme": "AA"}))
    assert [i for i in report.issues if i.code == "rhyme"]


def test_requests_never_ask_to_rhyme_with_the_word_before_a_number():
    from ashugh.fit import requests_for

    text = "I was born in '99,\nAnd I like to walk the street\n"
    reqs = requests_for(text, from_dict({"language": "en", "rhyme": "AA", "syllables": 7}))
    for r in reqs:
        assert "in" not in r.rhyme_with


@pytest.mark.parametrize(
    "text,expected",
    [
        ("born in '99,", True),
        ("born in '99 (oh yeah)", True),
        ("at 5 tonight", False),
        ("24/7", True),
    ],
)
def test_ends_in_number(text, expected):
    from ashugh.scan import ends_in_number

    assert ends_in_number(text) is expected


@pytest.mark.parametrize(
    "token,size,stress,shown",
    [
        ("ChatGPT", 4, 3, "Chat-G-P-T"),
        ("OpenAI", 4, 3, "O-pen-A-I"),
        ("MrBeast", 3, 2, "M-r-Beast"),  # Mr is mister
        ("SpaceX", 2, 0, "Space-X"),
    ],
)
def test_a_name_run_together_from_words_and_capitals(token, size, stress, shown):
    from ashugh.lang import en

    w = en.analyze_word(token)
    assert not w.guessed
    assert w.size == size and w.readings[0].stress == stress
    assert "-".join(s.text for s in w.syllables) == shown


@pytest.mark.parametrize("token,size", [("DeShawn", 2), ("LaToya", 3)])
def test_a_name_with_a_short_prefix_is_not_split_into_words(token, size):
    from ashugh.lang import en

    w = en.analyze_word(token)
    assert w.size == size and w.readings[0].source != "rule"  # not De + Shawn


@pytest.mark.parametrize(
    "token,size",
    [
        ("Mm-hmm", 2),
        ("Hey-ey-ey", 3),
        ("yeah-eah", 2),
        ("Mmm", 1),
        ("hmm", 1),
        ("Oh-oh-oh", 3),
        ("no-o-o", 3),
    ],
)
def test_vocables_are_read_without_warnings(token, size):
    from ashugh.lang import en

    w = en.analyze_word(token)
    assert w.size == size
    assert not w.guessed and all(r.source != "guess" for r in w.readings)


def test_an_echo_syllable_leaves_the_stress_on_the_word():
    from ashugh.lang import en

    w = en.analyze_word("Hey-ey-ey")
    assert w.readings[0].stress == 0


@pytest.mark.parametrize(
    "token,size", [("A-list", 2), ("B-side", 2), ("K-pop", 2), ("X-factor", 3)]
)
def test_a_letter_compound_is_stressed_on_its_letter(token, size):
    from ashugh.lang import en

    w = en.analyze_word(token)
    assert w.size == size and w.readings[0].stress == 0
    assert (
        any(r.stress == size - 1 or r.stress != 0 for r in w.readings[1:]) or len(w.readings) == 1
    )


@pytest.mark.parametrize(
    "a,b,rhyming",
    [
        ("and so we live", "five", False),
        ("and so we live", "give", True),
        ("lost in the wind", "find", False),
        ("lost in the wind", "sinned", True),
        ("I wanted to wind", "find", True),
        ("so hold me close", "dose", True),
        ("I close", "doze", True),
        ("all of our lives", "knives", True),
        ("he lives", "knives", False),
        ("Live", "five", True),  # no context: either reading
        ("Live", "give", True),
    ],
)
def test_a_vowel_heteronym_rhymes_as_its_context_reads_it(a, b, rhyming):
    assert (rhymes(a, b) >= 0.9) is rhyming


@pytest.mark.parametrize("word,size", [("statesmanlike", 3), ("wildflowers", 3)])
def test_cmudict_slips_are_corrected(word, size):
    from ashugh.lang import en

    w = en.analyze_word(word)
    assert w.size == size and w.readings[0].stress == 0


@pytest.mark.parametrize(
    "line,needle",
    [
        ("I walk alone (and cry", "parenthesis"),
        ("I see the light) tonight", "parenthesis"),
        ("*spoken* Hey you out there", "asterisks"),
    ],
)
def test_unbalanced_brackets_and_stage_directions_are_warned(line, needle):
    report = scan(line + "\n", Spec(language="en"))
    assert any(needle in i.message for i in report.issues), report.issues


def test_balanced_backing_vocals_are_not_warned():
    report = scan("I walk alone (alone) tonight\n", Spec(language="en"))
    assert not any("parenthes" in i.message or "asterisk" in i.message for i in report.issues)
