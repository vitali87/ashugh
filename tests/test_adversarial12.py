"""Round 12's adversarial findings: input that broke the tools."""

import pytest

from ashugh import lyrics, suno
from ashugh.scan import scan
from ashugh.spec import from_dict


def sections(text: str) -> list[tuple[str, str, str]]:
    return [(ln.text, ln.section, ln.key) for ln in lyrics.parse(text)]


@pytest.mark.parametrize(
    "tag",
    [
        "[Verse 1] [Male Vocal]",
        "[Verse 1](softly)",
        "[Verse 1]  (x2)  [Whispered]",
        "[Verse 1][Guitar]",
    ],
)
def test_a_tag_line_with_a_second_tag_or_an_aside_is_no_lyric(tag):
    assert sections(f"{tag}\nI walked along the river side\n") == [
        ("I walked along the river side", "Verse 1", "verse")
    ]


def test_a_second_tag_on_its_own_line_keeps_the_section():
    text = "[Chorus]\n[Female Vocal]\nOh river take me home\n"
    assert sections(text) == [("Oh river take me home", "Chorus", "chorus")]


def test_the_last_section_name_in_a_run_of_tags_opens_the_section():
    text = "[Intro]\n[Verse 1]\nI walked along the river side\n"
    assert sections(text)[0][2] == "verse"


def test_a_style_tag_after_lyric_lines_still_opens_a_stanza():
    text = "[Verse]\nI walked along\n[Spoken Word]\nAnd then I stopped\n"
    assert [ln.unit for ln in lyrics.parse(text)] == [0, 1]


def test_a_line_of_backing_vocals_alone_is_no_tag():
    assert not lyrics.is_tag("(oh) (yeah)")
    assert lyrics.is_tag("[Chorus] (softly)")
    assert not lyrics.is_tag("[Chorus] oh river")


def test_scan_counts_no_tag_text():
    rep = scan(
        "[Verse 1] [Male Vocal]\nI walked along the river side\n", from_dict({"syllables": 8})
    )
    assert [lr.line.number for lr in rep.lines] == [2] and rep.ok


def test_suno_keeps_a_tag_line_with_an_aside_and_adds_no_tag():
    out = suno.format_song("[Chorus] (softly)\nOh river take me home\n", tags=True).text
    assert out == "[Chorus] (softly)\nOh river take me home\n"


def test_suno_names_each_section_tag_on_a_tag_line():
    out = suno.format_song("[Припев] [Женский вокал]\nЯ жду\n", tags=True).text
    assert out.splitlines()[0] == "[Chorus] [Женский вокал]"


@pytest.mark.parametrize(
    "tag, key",
    [
        ("Verse Two", "verse"),
        ("Verse 2 - Rap", "verse"),
        ("Chorus - Female", "chorus"),
        ("Chorus – Female", "chorus"),
        ("Post Chorus", "post-chorus"),
        ("Chorus II", "chorus"),
        ("Куплет 1 - тихо", "verse"),
        ("Pre-Chorus", "pre-chorus"),
    ],
)
def test_section_tag_variants_name_their_section(tag, key):
    assert lyrics.section_key(tag) == key


@pytest.mark.parametrize(
    "tag, name",
    [
        ("Verse Two", "Verse 2"),
        ("Verse 2 - Rap", "Verse 2 - Rap"),
        ("Chorus II", "Chorus 2"),
        ("Куплет 1 - тихо", "Verse 1 - тихо"),
        ("Post Chorus", "Post-Chorus"),
        ("Pre-Chorus", "Pre-Chorus"),
    ],
)
def test_section_tag_variants_get_suno_names(tag, name):
    assert lyrics.suno_tag(tag) == name


def test_a_tag_naming_no_section_is_left_alone():
    assert lyrics.suno_tag("Male Vocal") is None
    assert lyrics.suno_tag("Chorus Line Dance") is None


def counts(text: str, lang: str | None = None) -> list[tuple[int, str, int]]:
    """Each line's count, stress grid and number of words."""
    rep = scan(text, from_dict({"language": lang} if lang else {}))
    return [(lr.fit.count, lr.fit.grid, len(lr.line.words)) for lr in rep.lines]


def nfd(text: str) -> str:
    import unicodedata

    return unicodedata.normalize("NFD", text)


@pytest.mark.parametrize(
    "line, lang",
    [("Мой тёплый дом, ещё зимой", "ru"), ("A naïve café", "en"), ("Իմ տունը", "hy")],
)
def test_decomposed_letters_count_as_composed(line, lang):
    assert counts(nfd(line), lang) == counts(line, lang)


def test_suno_writes_decomposed_text_as_composed():
    plain = suno.format_song("Мой тёплый дом\n", tags=False).text
    assert suno.format_song(nfd("Мой тёплый дом\n"), tags=False).text == plain
    assert "̈" not in plain


@pytest.mark.parametrize("mark", ["´", "`", "‘", "′", "ʼ"])
def test_any_apostrophe_inside_a_word_is_an_apostrophe(mark):
    assert counts(f"I don{mark}t know", "en") == counts("I don't know", "en")


@pytest.mark.parametrize("dash", ["‐", "‑"])
def test_a_unicode_hyphen_inside_a_word_is_a_hyphen(dash):
    assert counts(f"по{dash}моему", "ru") == counts("по-моему", "ru")


@pytest.mark.parametrize("mark", ["­", "​", "‌", "‍", "⁠", "﻿"])
@pytest.mark.parametrize("word, lang", [("старых", "ru"), ("forever", "en"), ("սիրում", "hy")])
def test_an_invisible_character_inside_a_word_does_not_split_it(mark, word, lang):
    at = len(word) // 2
    assert counts(word[:at] + mark + word[at:], lang) == counts(word, lang)


def test_quotes_at_the_edges_of_a_word_stay_quotes():
    assert counts("‘Hello’ she said `softly`", "en") == counts("Hello she said softly", "en")


def test_cleaning_keeps_the_lines_where_they_are():
    rep = scan("I walk​\n­\nthe way\n", from_dict({"language": "en"}))
    assert [lr.line.number for lr in rep.lines] == [1, 3]


def test_syllables_tool_reads_a_spacing_acute_apostrophe():
    from ashugh.scan import analyze_lines
    from ashugh.spec import Spec

    (ln,) = analyze_lines("I don´t know", Spec(language="en"))
    assert [w.text for w in ln.words] == ["I", "don't", "know"]


def words_of(text: str, lang: str) -> list[tuple[str, int, bool]]:
    from ashugh.scan import analyze_lines
    from ashugh.spec import Spec

    (ln,) = analyze_lines(text, Spec(language=lang))
    return [(w.text, w.size, w.spelled) for w in ln.words]


@pytest.mark.parametrize("line", ["ВСЁ В СССР", "СССР", "Всё в СССР"])
def test_a_russian_abbreviation_with_no_vowel_is_spelled_even_in_capitals(line):
    assert words_of(line, "ru")[-1] == ("СССР", 4, True)


@pytest.mark.parametrize("line", ["WE LOVE THE MC", "WE LOVE THE TV", "I love the MC"])
def test_an_english_abbreviation_with_no_vowel_is_spelled_even_in_capitals(line):
    assert words_of(line, "en")[-1][1:] == (2, True)


@pytest.mark.parametrize(
    "line, word",
    [
        ("I love MY baby", "MY"),
        ("Tell me WHY", "WHY"),
        ("TELL ME WHY", "WHY"),
        ("I hit the GYM", "GYM"),
        ("I said HMM", "HMM"),
        ("SHE SAID SHH", "SHH"),
        ("I said PSST", "PSST"),
    ],
)
def test_a_capitalized_english_word_with_y_or_an_interjection_is_no_abbreviation(line, word):
    assert dict((t, s) for t, _, s in words_of(line, "en"))[word] is False


@pytest.mark.parametrize("line", ["Я сказал ХМ", "Я СКАЗАЛ ХМ", "НО ТСС"])
def test_a_russian_interjection_with_no_vowel_is_no_abbreviation(line):
    assert words_of(line, "ru")[-1][2] is False


def test_a_lone_vowelless_abbreviation_rhymes():
    from ashugh import meter, rhyme
    from ashugh.scan import analyze_lines
    from ashugh.spec import Spec

    lines = analyze_lines("СССР\nСША", Spec(language="ru"))
    assert all(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines)


DIGITS_SONG = "[Intro]\n1, 2, 3, 4!\nI walked along the river side\n"


def test_a_spec_derived_from_a_line_of_digits_loads_and_passes_its_song():
    from ashugh.spec import dumps, loads
    from ashugh.translate import derive_spec

    src = scan(DIGITS_SONG, from_dict({"language": "en"}))
    data = derive_spec(src, {"syllables", "meter", "rhyme", "endings"})
    table = data["stanza"]["1"]
    assert table["syllables"] == [0, 8] and table["endings"][0] == "-"
    spec = loads(dumps({"language": "en", **data}))
    assert not [i for i in scan(DIGITS_SONG, spec).issues if i.severity == "error"]


def test_a_zero_in_a_syllable_list_leaves_that_line_free():
    rep = scan("I walk\nI walked along the river side\n", from_dict({"syllables": [0, 8]}))
    assert rep.ok


@pytest.mark.parametrize("value", [0, [0, 0], "0"])
def test_a_spec_with_no_count_above_zero_is_refused(value):
    from ashugh.spec import SpecError

    with pytest.raises(SpecError, match="syllables"):
        from_dict({"syllables": value})


@pytest.mark.parametrize("value", ["²", "٣", [8, -1]])
def test_a_count_that_is_no_plain_number_is_refused_by_name(value):
    from ashugh.spec import SpecError

    with pytest.raises(SpecError, match="song.toml: syllables"):
        from_dict({"syllables": value}, "song.toml")


def test_translate_takes_a_source_with_a_line_of_digits():
    from ashugh.proposers import StaticProposer
    from ashugh.translate import translate_song

    proposer = StaticProposer({2: ["Раз, два, три, четыре!"], 3: ["Я шёл по берегу реки"]})
    result = translate_song(DIGITS_SONG, "ru", proposer, rounds=1)
    assert "Я шёл по берегу реки" in result.text


@pytest.mark.parametrize(
    "old, new",
    [
        ("I walked the long river side (oh) (yeah)", "I walked the riverside (oh) (yeah)"),
        ("I walked the long river side (oh), (yeah)!", "I walked the riverside (oh), (yeah)!"),
        ("I walked the long river side. (oh) (yeah)", "I walked the riverside. (oh) (yeah)"),
    ],
)
def test_a_replaced_line_keeps_every_backing_vocal_that_ends_it(old, new):
    from ashugh.fit import replace_lines

    assert replace_lines(old + "\n", {1: "I walked the riverside"}) == new + "\n"


def test_pick_keeps_both_backing_vocals():
    from ashugh.fit import fit_song
    from ashugh.proposers import StaticProposer

    text = "I walked along the long river side (oh) (yeah)\n"
    proposer = StaticProposer({1: ["I walked along the riverside"]})
    res = fit_song(text, from_dict({"language": "en", "syllables": 8}), proposer, rounds=1)
    assert res.text == "I walked along the riverside (oh) (yeah)\n"


ODD_VALUES = [["ru"], {"a": 1}, 1.5, True, None, "²", [], [[8]], {"verse": 5}, -1, 10**30]


@pytest.mark.parametrize("value", ODD_VALUES)
@pytest.mark.parametrize(
    "key",
    [
        "language",
        "syllables",
        "tolerance",
        "meter",
        "feet",
        "rhyme",
        "endings",
        "min_rhyme",
        "forbid_final",
        "section",
        "stanza",
        "lexicon",
    ],
)
def test_a_spec_value_of_any_type_is_read_or_refused_by_name(key, value):
    from ashugh.spec import SpecError

    for data in ({key: value}, {"section": {"verse": {key: value}}}, {"stanza": {"²": {}}}):
        try:
            from_dict(data, "song.toml")
        except SpecError as e:
            assert "song.toml" in str(e)


@pytest.mark.parametrize(
    "policy",
    [
        {"hy": {"words": ["x"]}},
        {"hy": {"words": "x"}},
        {"ru": {"words": [1]}},
        {"hy": {"default": ["latin"]}},
        {"hy": {"words": {"x": ["latin"]}}},
    ],
)
def test_a_malformed_policy_is_refused_with_a_message(policy):
    with pytest.raises(ValueError, match="policy"):
        suno.format_song("Իմ տունը\n", policy=policy)


def test_mcp_survives_a_huge_integer():
    from test_servers_robust import PING, mcp_run

    big = '{"jsonrpc":"2.0","id":1,"method":"ping","params":{"x":' + "9" * 5000 + "}}"
    replies = mcp_run(big, PING)
    assert replies[0]["error"]["code"] == -32700 and replies[-1]["id"] == 99


def test_lsp_survives_deep_nesting_and_a_huge_length():
    from test_servers_robust import frame, lsp_run, msg

    deep = b"[" * 100000 + b"]" * 100000
    huge = b"Content-Length: 99999999999999999999\r\n\r\n{}"
    stream = frame(deep) + huge + frame(msg(id=7, method="shutdown"))
    assert [m.get("id") for m in lsp_run(stream)] == [7]


def test_lsp_hover_reads_the_text_of_its_moment():
    from test_servers_robust import frame, lsp_run, msg

    def change(text: str) -> bytes:
        params = {"textDocument": {"uri": "u"}, "contentChanges": [{"text": text}]}
        return frame(msg(method="textDocument/didChange", params=params))

    opened = {"textDocument": {"uri": "u", "text": "x"}}
    hover = {"textDocument": {"uri": "u"}, "position": {"line": 0, "character": 0}}
    stream = (
        frame(msg(method="textDocument/didOpen", params=opened))
        + change("I walk the way")
        + frame(msg(id=1, method="textDocument/hover", params=hover))
        + change("I walk the long and winding way")
        + frame(msg(id=2, method="shutdown"))
    )
    (reply,) = [m for m in lsp_run(stream) if m.get("id") == 1]
    assert reply["result"]["contents"]["value"].startswith("**4 syllables**")


def test_lsp_names_a_spec_with_a_list_for_its_language(tmp_path):
    from ashugh import lsp

    song, spec = tmp_path / "song.txt", tmp_path / "song.toml"
    spec.write_text('language = ["ru"]\n', encoding="utf-8")
    server = lsp.Server()
    open_ = {"textDocument": {"uri": song.as_uri(), "text": "Я жду\n"}}
    (pub,) = server.handle({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": open_})
    (diag,) = pub["params"]["diagnostics"]
    assert "language" in diag["message"] and diag["code"] == "spec"


@pytest.mark.parametrize("name", ["iamb100000000", "iamb51"])
def test_a_meter_of_absurd_length_is_refused(name):
    from ashugh.spec import SpecError

    with pytest.raises(SpecError, match="at most 50 feet"):
        from_dict({"meter": name})


def test_a_long_armenian_cluster_is_cut_in_time_linear_in_its_length():
    import time

    from ashugh.lang import hy

    start = time.perf_counter()
    w = hy.analyze_word("բժշկ" * 30 + "ել")
    assert time.perf_counter() - start < 2  # every cut tried was 2^n: a minute at 30 letters
    assert w.size == 46
    short = hy.analyze_word("բժշկ" * 6 + "ել")
    assert "-".join(s.text for s in short.syllables).startswith("բըժ-շըկբ-ժըշկ")


@pytest.mark.parametrize("a, b", [("我爱你", "中国"), ("κόσμε", "σου"), ("שלום", "עולם")])
def test_words_of_a_script_not_read_do_not_rhyme(a, b):
    from ashugh import meter, rhyme
    from ashugh.scan import analyze_lines
    from ashugh.spec import Spec

    lines = analyze_lines(f"{a}\n{b}", Spec())
    assert all(rhyme.tails(ln, meter.fit(ln.words, "free")) == [] for ln in lines)


def test_a_line_in_a_script_not_read_is_left_out_of_the_rhyme_check():
    rep = scan("Γεια σου κόσμε\nI love you\nשלום עולם\nand I do\n", from_dict({"rhyme": "ABAB"}))
    assert not [i for i in rep.issues if i.severity == "error"]
    assert [lr.letter for lr in rep.lines] == ["-", "A", "-", "A"]
    assert all("rhyme unknown" in i.detail for i in rep.issues if i.code == "script")


def test_suno_marks_an_ambiguous_stress_in_capitals_with_an_acute():
    res = suno.format_song("Я ВИЖУ ЗАМОК\n", tags=False)
    lower = suno.format_song("Я вижу замок\n", tags=False)
    assert "́" in res.text and any(n.kind == "stress" for n in res.notes)
    marked = lower.text.split()[-1]  # замОк or зАмок: the same vowel takes the acute
    at = next(k for k, ch in enumerate(marked) if ch.isupper())
    assert res.text.split()[-1][at + 1] == "́"


def test_suno_leaves_a_writers_capital_mark_as_it_is():
    assert "́" not in suno.format_song("Я вижу замОк\n", tags=False).text


@pytest.mark.parametrize(
    "line, words",
    [
        ("I see (and twinkle (on the) milky way) the stars", ["I", "see", "the", "stars"]),
        ("I see ((oh)) the stars", ["I", "see", "the", "stars"]),
        ("I see (oh) (and (yeah)) stars", ["I", "see", "stars"]),
        ("I see (oh stars", ["I", "see", "oh", "stars"]),
        ("I see oh) stars", ["I", "see", "oh", "stars"]),
    ],
)
def test_a_backing_vocal_may_hold_parentheses_of_its_own(line, words):
    assert lyrics.tokenize(line) == words


def test_digits_inside_a_nested_backing_vocal_are_not_flagged():
    assert not lyrics.has_digits("I see (and (x2) twinkle 4 you) the stars")


def test_a_replaced_line_keeps_a_nested_backing_vocal():
    from ashugh.fit import replace_lines

    old = "I walked the long river side (and (oh) yeah)\n"
    assert replace_lines(old, {1: "I walked the riverside"}) == (
        "I walked the riverside (and (oh) yeah)\n"
    )


def test_suno_reads_a_nested_backing_vocal_as_one():
    out = suno.format_song("Я жду тебя (моё (моё) моё)\n", tags=False).text
    assert out.endswith("(моё (моё) моё)\n")


@pytest.mark.parametrize(
    "line", ["I love you so x2", "I love you so ×2", "Я жду тебя х2!", "I go 2x"]
)
def test_a_repeat_mark_ending_a_line_is_no_digit(line):
    assert not lyrics.has_digits(line)


def test_digits_inside_a_line_are_still_flagged():
    assert lyrics.has_digits("I got 2 hearts x2")


@pytest.mark.parametrize("encoding", ["utf-16", "utf-16-le", "utf-16-be"])
def test_the_cli_reads_a_utf16_file_with_its_byte_order_mark(tmp_path, encoding, capsys):
    from ashugh.cli import main

    song = tmp_path / "song.txt"
    bom = {"utf-16-le": b"\xff\xfe", "utf-16-be": b"\xfe\xff"}.get(encoding, b"")
    song.write_bytes(bom + "I walk the way\n".encode(encoding))
    assert main(["scan", str(song), "--syllables", "4"]) == 0
    assert "4 syllables" not in capsys.readouterr().err


def test_the_cli_names_a_file_that_is_not_text(tmp_path, capsys):
    from ashugh.cli import main

    song = tmp_path / "song.txt"
    song.write_bytes(b"I walk \xff\xfe\x00 the way\n")
    assert main(["scan", str(song)]) == 2
    err = capsys.readouterr().err
    assert "song.txt" in err and "UTF-8" in err


def test_requests_warn_of_a_slot_no_line_can_fill(tmp_path, capsys):
    from ashugh.cli import main

    song = tmp_path / "song.txt"
    song.write_text("I walk the way\nand talk all day\n", encoding="utf-8")
    args = ["requests", str(song), "--syllables", "8", "--meter", "iamb4", "--endings", "f"]
    assert main(args) == 0
    assert "no line can pass this slot" in capsys.readouterr().err


def test_mcp_requests_carry_the_spec_warnings():
    from test_servers_robust import tool

    spec = 'syllables = 8\nmeter = "iamb4"\nendings = "f"\n'
    failed, data = tool("requests", lyrics="I walk the way\nand talk all day\n", spec=spec)
    assert not failed and any("no line can pass" in w for w in data["warnings"])


def warnings_of(text: str, spec: dict) -> list[tuple[int, str, str]]:
    rep = scan(text, from_dict({"language": "en", **spec}))
    return [(i.line, i.code, i.message) for i in rep.issues if i.severity == "warning"]


@pytest.mark.parametrize("line", ["[Bridge] I walk the way", "[[Chorus]]", "[Verse", "[Outro]]"])
def test_brackets_in_a_sung_line_are_warned_about(line):
    found = warnings_of(f"{line}\nI talk all day\n", {})
    assert (1, "tag", "brackets in a sung line") in found


def test_brackets_in_a_backing_vocal_are_not():
    assert not [w for w in warnings_of("I walk the way (oh [yeah])\n", {}) if w[1] == "tag"]


FOUR = "I walk the way\nI see the sun\nand talk all day\nmy work is done\n"
SIX = FOUR + "I sing my song\nand then I rest\n"


def test_a_scheme_that_names_each_letter_once_warns_on_a_longer_stanza():
    found = warnings_of(FOUR, {"rhyme": "AB"})
    assert any(code == "scheme" and "no line must rhyme" in m for _, code, m in found)


def test_a_scheme_that_leaves_a_line_of_its_repeat_alone_warns():
    found = warnings_of(SIX, {"rhyme": "ABAB"})
    assert any(code == "scheme" and "fits 4" in m for _, code, m in found)


@pytest.mark.parametrize(
    "text, scheme", [(SIX, "AABB"), (FOUR + FOUR, "ABCB"), (FOUR, "ABCD"), (FOUR, "ABAB")]
)
def test_a_scheme_that_fits_its_stanza_says_nothing(text, scheme):
    assert not [w for w in warnings_of(text, {"rhyme": scheme}) if w[1] == "scheme"]


@pytest.mark.parametrize("flag", ["--rhyme=", "--meter=", "--endings=", "--meter=free4"])
def test_an_empty_or_meaningless_rule_flag_is_refused(flag, tmp_path, capsys):
    from ashugh.cli import main

    song = tmp_path / "song.txt"
    song.write_text("I walk the way\n", encoding="utf-8")
    assert main(["scan", str(song), flag]) == 2
    assert "flags" in capsys.readouterr().err


@pytest.mark.parametrize("key", ["2.9", "true", "1_0", "²", "L1_0", "-1"])
def test_a_candidate_key_that_is_no_line_number_is_refused(key, tmp_path):
    from ashugh.proposers import ProposerError, load_candidates

    path = tmp_path / "c.json"
    path.write_text("{" + f'"{key}"' + ': ["I walk"]}', encoding="utf-8")
    with pytest.raises(ProposerError, match="not a line number"):
        load_candidates(path)


@pytest.mark.parametrize("key", [2.9, True])
def test_a_candidate_line_that_is_no_whole_number_is_refused(key):
    from ashugh.proposers import ProposerError, parse_candidates

    with pytest.raises(ProposerError, match="not a line number"):
        parse_candidates([{"line": key, "candidates": ["I walk"]}])


@pytest.mark.parametrize(
    "mixed, plain",
    [
        ("oкон", "окон"),
        ("мoлoкo", "молоко"),
        ("hеllo", "hello"),
        ("cтaрых", "старых"),
        ("Mосква-Moscow", "Москва-Moscow"),
        ("МОСКBА", "МОСКВА"),
    ],
)
def test_a_look_alike_letter_from_the_other_alphabet_is_read_as_its_twin(mixed, plain):
    assert lyrics.clean(mixed) == plain


@pytest.mark.parametrize("word", ["iPhone", "Ёж", "XXL", "мой-my", "SMSка", "VIPовский", "DJем"])
def test_a_word_of_two_alphabets_without_twins_is_left_alone(word):
    assert lyrics.clean(word) == word


def test_syl_reads_stdin_as_scan_does(monkeypatch, capsys):
    import io

    from ashugh.cli import main

    raw = io.BytesIO(b"I walk \xff the way\n")
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(raw, encoding="utf-8", errors="ignore"))
    assert main(["syl"]) == 2
    assert "not UTF-8" in capsys.readouterr().err


def test_pick_says_when_a_backing_vocal_inside_a_line_is_left_out():
    from ashugh.fit import fit_song
    from ashugh.proposers import StaticProposer

    text = "I walked (oh) along the long river side\n"
    proposer = StaticProposer({1: ["I walked along the riverside"]})
    res = fit_song(text, from_dict({"language": "en", "syllables": 8}), proposer, rounds=1)
    assert res.text == "I walked along the riverside\n"
    assert any("L1" in w and "(oh)" in w for w in res.warnings)


def test_pick_says_nothing_of_a_backing_vocal_it_keeps():
    from ashugh.fit import fit_song
    from ashugh.proposers import StaticProposer

    text = "I walked along the long river side (oh)\n"
    proposer = StaticProposer({1: ["I walked along the riverside"]})
    res = fit_song(text, from_dict({"language": "en", "syllables": 8}), proposer, rounds=1)
    assert res.text.endswith("(oh)\n") and res.warnings == []


def test_pick_does_not_rhyme_a_line_on_another_form_of_its_partners_word():
    from ashugh.fit import fit_song
    from ashugh.proposers import StaticProposer

    text = "Я слышу стук родного сердца\nИ бьётся радостно душа\n"
    proposer = StaticProposer({2: ["И бьётся радостное сердце", "И бьётся радостно, как дверца"]})
    res = fit_song(text, from_dict({"language": "ru", "rhyme": "AA"}), proposer, rounds=1)
    assert res.text.splitlines()[1] == "И бьётся радостно, как дверца"


def test_a_song_written_with_a_form_rhyme_keeps_it():
    from ashugh.fit import fit_song
    from ashugh.proposers import StaticProposer

    text = "Я слышу стук родного сердца\nИ бьётся радостное сердце\n"
    res = fit_song(text, from_dict({"language": "ru", "rhyme": "AA"}), StaticProposer({}))
    assert res.text == text and not res.unresolved
