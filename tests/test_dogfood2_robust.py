"""Robustness fixes from the second dogfooding round."""

import json

import pytest

from ashugh.cli import main


def test_a_spec_that_is_not_utf8_is_a_spec_error(tmp_path):
    from ashugh.spec import SpecError, load

    bad = tmp_path / "song.toml"
    bad.write_bytes(b'language = "ru"\n# caf\xe9\n')
    with pytest.raises(SpecError, match="UTF-8"):
        load(bad)


def test_the_language_server_reports_a_bad_sibling_spec(tmp_path):
    from ashugh.lsp import Server

    (tmp_path / "song.toml").write_bytes(b"# caf\xe9\n")
    song = tmp_path / "song.txt"
    msg = {
        "jsonrpc": "2.0",
        "method": "textDocument/didOpen",
        "params": {"textDocument": {"uri": song.as_uri(), "version": 1, "text": "Я жду"}},
    }
    (publish,) = Server().handle(msg)
    (diag,) = publish["params"]["diagnostics"]
    assert "UTF-8" in diag["message"]


@pytest.mark.parametrize(
    "tool,args",
    [
        ("scan", {"lyrics": "x", "lang": "fr"}),
        ("rhyme", {"a": "a", "b": "b", "lang": "zz"}),
        ("spec_template", {"lang": "xx"}),
    ],
)
def test_mcp_refuses_unknown_languages(tool, args):
    from ashugh.mcp import Server

    r = Server().handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": args},
        }
    )
    assert r is not None
    result = r["result"]
    assert (
        result["isError"]
        and "lang must be one of" in json.loads(result["content"][0]["text"])["error"]
    )


def test_mcp_pick_lists_lang_in_its_schema():
    from ashugh.mcp import TOOLS

    assert "lang" in TOOLS["pick"][1]["properties"]


def test_probes_do_not_repeat_the_same_spelling():
    from ashugh import probe

    plan = probe.make_probes(["облака"], "ru")
    lyrics = [p.lyrics for p in plan]
    assert len(lyrics) == len(set(lyrics))


def test_eval_apply_keeps_crlf_and_drops_a_bom(tmp_path):
    from ashugh import evaluate
    from ashugh.spec import from_dict

    drafts, out = tmp_path / "drafts", tmp_path / "out"
    drafts.mkdir()
    (drafts / "t.txt").write_bytes("﻿I walk along the river\r\nAnd wait for you\r\n".encode())
    task = evaluate.Task("t", "en", "a song", from_dict({"language": "en"}), "t.toml")
    evaluate.apply_candidates([task], drafts, {}, out)
    data = (out / "t.txt").read_bytes()
    assert data.count(b"\r\n") == 2 and not data.startswith("﻿".encode())


@pytest.mark.parametrize("flag", [["-n", "0"], ["--rounds", "0"], ["-n", "-2"]])
def test_counts_on_the_command_line_must_be_positive(tmp_path, capsys, flag):
    song = tmp_path / "s.txt"
    song.write_text("I walk along the river\n", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        main(["fit", str(song), "--proposer", "cmd:true", *flag])
    assert e.value.code == 2
    assert "must be 1 or more" in capsys.readouterr().err


@pytest.mark.parametrize(
    "word,count",
    [
        ("café", 2),
        ("naïve", 2),
        ("José", 2),
        ("résumé", 3),
        ("Beyoncé", 3),
        ("Zoë", 2),
        ("Renée", 2),
        ("shouldn't've", 3),
        ("couldn't've", 3),
        ("we'd've", 2),
    ],
)
def test_accented_english_and_stacked_contractions(word, count):
    from ashugh.lang import en

    assert en.analyze_word(word).size == count


@pytest.mark.parametrize(
    "word,pieces",
    [
        ("laughing", "laugh-ing"),
        ("weighing", "weigh-ing"),
        ("couldn't", "could-n't"),
        ("wouldn't", "would-n't"),
        ("heartache", "heart-ache"),
        ("moonlight", "moon-light"),
        ("beautiful", "beau-ti-ful"),
        ("reading", "rea-ding"),
        ("little", "lit-tle"),
    ],
)
def test_english_spelling_pieces(word, pieces):
    from ashugh.lang import en

    assert "-".join(s.text for s in en.analyze_word(word).syllables) == pieces


def test_split_all_follows_the_lines_short_forms():
    from ashugh import suno
    from ashugh.spec import from_dict

    line = "Every fire in our hearts is burning"
    spec = from_dict({"language": "en", "syllables": 9})
    out = suno.format_song(line + "\n", spec, split="all", tags=False).text.strip()
    pieces = [p for word in out.split() for p in word.split("-")]
    assert len(pieces) == 9, out


def test_probe_ties_keep_sunos_default_spelling():
    from ashugh import probe

    plan = probe.make_probes(["замок", "дорога"], "ru")
    same = {p.id: p.word for p in plan}  # text cannot show stress: every mode ties
    assert probe.score(plan, same).policy["ru"]["default"] == "caps"
    hy = probe.make_probes(["սպասել"], "hy")
    heard = {p.id: "spasel" for p in hy}
    assert probe.score(hy, heard).policy["hy"]["default"] in ("script", "schwa", "latin")
