"""Round 15 of dogfooding, English: what a songwriter found wrong."""

import unicodedata

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
    text = "Ravenshore in the underworld\nAnd Duskwalker\n"
    report = scan(text, from_dict({"language": "en"}))
    said = [i for i in report.issues if "read as" in i.message]
    assert [i.message for i in said] == [
        "«Ravenshore» read as raven + shore",
        "«Duskwalker» read as dusk + walker",
    ]
    assert "lexicon" in said[0].detail and said[0].data["parts"] == ["raven", "shore"]


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


@pytest.mark.parametrize(
    "line,word,size",
    [
        ("I LOVE NYC", "NYC", 3), ("LOVE YOU, NY", "NY", 2), ("TYVM MY FRIEND", "TYVM", 4),
        ("I LOVE NYC", "LOVE", 1), ("WHY THE SKY", "WHY", 1), ("FEEL THE RHYTHM", "RHYTHM", 2),
        ("IN THE GYMS", "GYMS", 1), ("MY MYTHS", "MYTHS", 1),
    ],
)  # fmt: skip
def test_capitals_with_only_a_y_are_letters_unless_a_word(line, word, size):
    words = scan(line + "\n", from_dict({"language": "en"})).lines[0].line.words
    assert next(w for w in words if w.text == word).size == size


@pytest.mark.parametrize(
    "a,b",
    [
        ("smote", "wrote"), ("clave", "grave"), ("zorb", "orb"), ("shawty", "naughty"),
        ("aight", "night"), ("homie", "foamy"), ("bruh", "duh"), ("fam", "jam"),
        ("swag", "bag"), ("hella", "fella"), ("skrrt", "dirt"), ("canst", "manse"),
    ],
)  # fmt: skip
def test_slang_archaic_and_guessed_words_rhyme_as_they_sound(a, b):
    assert rhymes(a, b) >= rhyme.THRESHOLD["near"], (a, b)


@pytest.mark.parametrize(
    "word",
    "tryna finna imma bouta aight bruh fam bestie skrrt ayy yuh swag shawty homie hella "
    "canst couldst wouldst shouldst hadst didst mayst mightst wast saith seest goeth goest "
    "smote prithee forsooth alack".split(),
)
def test_common_slang_and_archaic_forms_are_known(word):
    from ashugh.lang import en

    assert not en.analyze_word(word).guessed


def test_a_word_still_unknown_is_still_named():
    report = scan("I glorped the zibber\n", from_dict({"language": "en"}))
    assert {i.data.get("word") for i in report.issues if "unknown" in i.message} == {
        "glorped",
        "zibber",
    }


@pytest.mark.parametrize(
    "word,shown",
    [
        ("touché", "tou-ché"), ("naïve", "na-ḯve"), ("café", "ca-fé"),
        ("Zoë", "Zó-ë"), ("coöperate", "co-ö́p-e-rate"), ("touche", "touche"),
    ],
)  # fmt: skip
def test_an_accented_vowel_is_sung_and_marked_where_written(word, shown):
    from ashugh.lang import en

    w = en.analyze_word(word)
    assert unicodedata.normalize("NFD", w.sung(w.readings[0].stress, mark=True)) == (
        unicodedata.normalize("NFD", shown)
    )


def test_a_russian_short_i_is_never_marked_as_a_vowel():
    from ashugh.model import mark_stress

    assert mark_stress("йод") == "йо́д"


def test_a_reader_that_stops_early_is_no_error(tmp_path):
    import subprocess
    import sys

    song = tmp_path / "big.txt"
    song.write_text("I walk along the river side\n" * 100, encoding="utf-8")
    cmd = [sys.executable, "-m", "ashugh", "scan", str(song), "--json"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdout is not None and proc.stderr is not None
    proc.stdout.readline()
    proc.stdout.close()  # head -1
    err = proc.stderr.read().decode()
    assert proc.wait(timeout=60) == 0 and "Broken pipe" not in err, err


def _scan_into(raw, tmp_path, monkeypatch):
    """Run scan --json with stdout buffered over `raw`, big enough to hold it all."""
    import io
    import sys

    from ashugh import cli

    song = tmp_path / "song.txt"
    song.write_text("I walk along the river side\n", encoding="utf-8")
    out = io.TextIOWrapper(io.BufferedWriter(raw, 1 << 20), encoding="utf-8")
    monkeypatch.setattr(sys, "stdout", out)
    return cli.main(["scan", str(song), "--json"]), out


def test_a_reader_gone_before_the_last_flush_is_no_error(tmp_path, monkeypatch):
    import io
    import os

    # The whole answer still sits in the buffer when the scan returns, so the
    # first write to the closed pipe is the last flush, as at a fast reader's exit.
    read_end, write_end = os.pipe()
    os.close(read_end)
    code, out = _scan_into(io.FileIO(write_end, "w"), tmp_path, monkeypatch)
    assert code == 0
    out.close()  # nothing is left to fail on the closed pipe once main returns


def test_a_full_disk_on_the_last_flush_is_an_error(tmp_path, monkeypatch, capsys):
    import errno
    import io

    class Full(io.RawIOBase):
        full = True

        def writable(self):
            return True

        def write(self, b):
            if self.full:
                raise OSError(errno.ENOSPC, "No space left on device")
            return len(b)

    # Negative: only a reader that has gone is quiet; a write that fails for
    # any other reason is reported and exits 2, not 0.
    raw = Full()
    try:
        code, _ = _scan_into(raw, tmp_path, monkeypatch)
        assert code == 2
        assert "No space left on device" in capsys.readouterr().err
    finally:
        raw.full = False  # the buffer's own close may flush once the test is done


def test_a_line_that_fails_its_meter_gets_no_note_that_it_fits():
    report = scan("We sat for hours\n", from_dict({"language": "en", "meter": "trochee"}))
    assert not [i for i in report.issues if i.message.startswith("fits if")]
    assert [i for i in report.issues if i.code == "meter"]


def test_a_line_the_drop_lets_pass_keeps_its_note():
    spec = from_dict({"language": "en", "meter": "trochee", "feet": 4})
    report = scan("Every heartbeat calls your name\n", spec)
    assert report.lines[0].ok
    assert [i for i in report.issues if i.message.startswith("fits if «Every»")]


def test_an_unresolved_chorus_copy_names_the_line_it_follows():
    from ashugh.fit import fit_song
    from ashugh.proposers import StaticProposer

    text = (
        "[Chorus]\nHold on tight\nWe will dance all through the night\n\n"
        "[Chorus]\nHold on tight\nWe will dance all through the night\n"
    )
    spec = from_dict({"language": "en", "syllables": [3, 5]})
    result = fit_song(text, spec, StaticProposer({3: ["We will dance all through the day"]}))
    why = {u.line: u.reasons for u in result.unresolved}
    assert why[7][0].startswith("repeats L3") and "no candidates given" not in why[7][0]


@pytest.mark.parametrize(
    "data,message",
    [
        ({"lines": "nope"}, '"lines" must be a list'),
        ({"lines": [{"candidates": ["Hold on"]}]}, 'has no "id"'),
        ({"3": [{"text": "Hold on", "faithfulness": "high"}]}, 'faithfulness "high"'),
        ({"3": [{"text": "Hold on", "faithfulness": float("nan")}]}, "faithfulness NaN"),
        ({"3": [{"text": "Hold on", "faithfulness": float("-inf")}]}, "faithfulness -Infinity"),
        ({"3": [{"text": "Hold on", "faithfulness": 1.5}]}, "faithfulness 1.5"),
    ],
)  # fmt: skip
def test_a_malformed_candidates_file_is_named_plainly(data, message):
    from ashugh.proposers import ProposerError, parse_candidates

    with pytest.raises(ProposerError) as e:
        parse_candidates(data, "c.json")
    assert message in str(e.value) and "None" not in str(e.value)


def test_good_candidates_files_still_load():
    from ashugh.proposers import parse_candidates

    data = {"lines": [{"id": "L3", "candidates": [{"text": "Hold on", "faithfulness": 0.7}]}]}
    assert parse_candidates(data) == {3: [{"text": "Hold on", "faithfulness": 0.7}]}
    assert parse_candidates({"3": ["Hold on", {"text": "Hold tight"}]}) == {
        3: ["Hold on", {"text": "Hold tight"}]
    }


def test_a_proposer_answering_a_line_nobody_asked_about_is_warned(tmp_path):
    import json
    import sys

    from ashugh.fit import fit_song
    from ashugh.proposers import CommandProposer

    script = tmp_path / "p.py"
    answer = {"lines": [{"id": "L77", "candidates": ["Something new"]}]}
    script.write_text(f"import sys; sys.stdin.read(); print({json.dumps(json.dumps(answer))})")
    spec = from_dict({"language": "en", "syllables": 3})
    result = fit_song("Hold on to me tight\n", spec, CommandProposer([sys.executable, str(script)]))
    assert any("L77" in w and "no request" in w for w in result.warnings)


def test_mcp_translate_names_a_bad_min_rhyme_without_a_spec():
    import json

    from ashugh.mcp import Server

    server = Server()
    msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/call"}
    args = {"lyrics": "Hold on tight\n", "to": "ru", "min_rhyme": "great"}
    msg["params"] = {"name": "translate", "arguments": args}
    response = server.handle(msg)
    assert response is not None
    result = response["result"]
    text = json.loads(result["content"][0]["text"])["error"]
    assert result["isError"] and "min_rhyme must be one of" in text and "spec" not in text


@pytest.mark.parametrize(
    "text", ["rock 'n' roll", "fish ’n’ chips", "salt n pepper", "rock 'n roll"]
)
def test_a_separate_n_is_an_unstressed_and(text):
    words = scan(text + "\n", from_dict({"language": "en"})).lines[0].line.words
    n = words[1]
    assert n.clitic and n.readings[0].phones == ("ə", "n")


def test_n_inside_a_hyphenated_word_still_reads_as_and():
    words = scan("rock-'n'-roll\n", from_dict({"language": "en"})).lines[0].line.words
    assert [w.text for w in words] == ["rock", "n", "roll"] and words[1].clitic


@pytest.mark.parametrize(
    "word,lang,message",
    [
        ("Մկրտիչ", "ru", "written in hy, not ru: use --lang hy"),
        ("облако", "hy", "written in ru, not hy: use --lang ru"),
    ],
)
def test_probe_make_refuses_a_word_in_another_language(word, lang, message):
    from ashugh.probe import make_probes

    with pytest.raises(ValueError) as e:
        make_probes([word], lang)
    assert message in str(e.value)


def test_probe_make_still_takes_words_in_its_language():
    from ashugh.probe import make_probes

    assert make_probes(["облака"], "ru") and make_probes(["Մկրտիչ"], "hy")
    assert make_probes(["iPhone"], "ru")  # a brand in a Russian song


def test_translate_warns_when_the_source_language_given_is_not_the_one_written():
    from ashugh.proposers import StaticProposer
    from ashugh.translate import translate_song

    source = "Hush now my baby\nThe night is so deep\n"
    result = translate_song(source, "hy", StaticProposer({}), rounds=1, source_lang="ru")
    assert result.warnings and "written in en, but was read as ru" in result.warnings[0]
    result = translate_song(source, "hy", StaticProposer({}), rounds=1, source_lang="en")
    assert not any("was read as" in w for w in result.warnings)
