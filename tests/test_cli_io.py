"""Files as a songwriter's editor saves them: CRLF, a BOM; and the CLI's messages."""

import json

import pytest

from ashugh.cli import main

SONG = "[Verse]\r\nI walk along the river\r\nAnd wait for you all day\r\n"


def test_pick_keeps_crlf_in_the_file_and_on_stdout(tmp_path, capsys):
    song = tmp_path / "s.txt"
    song.write_bytes(SONG.encode())
    cands = tmp_path / "c.json"
    cands.write_text(json.dumps({"3": ["And wait for you all the day"]}), encoding="utf-8")
    out = tmp_path / "out.txt"
    main(["pick", str(song), "--syllables", "7", "--candidates", str(cands), "-o", str(out)])
    assert out.read_bytes().count(b"\r\n") == 3 and b"\n" not in out.read_bytes().replace(
        b"\r\n", b""
    )
    capsys.readouterr()
    main(["pick", str(song), "--syllables", "7", "--candidates", str(cands)])
    printed = capsys.readouterr().out
    assert printed.count("\r\n") == 3


def test_suno_keeps_crlf_when_it_adds_tags(tmp_path, capsys):
    song = tmp_path / "s.txt"
    song.write_bytes(b"la la la\r\nla la la\r\n\r\nno no no\r\n\r\nla la la\r\nla la la\r\n")
    main(["suno", str(song)])
    out = capsys.readouterr().out
    assert "[Chorus]\r\n" in out and "\n" not in out.replace("\r\n", "")


def test_a_bom_does_not_hide_the_first_tag(tmp_path, capsys):
    song = tmp_path / "s.txt"
    song.write_bytes("﻿[Verse 1]\nI walk along the river\n".encode())
    assert main(["scan", str(song), "--json"]) == 0
    rep = json.loads(capsys.readouterr().out)
    assert rep["sections"][0]["section"] == "Verse 1"
    assert [ln["text"] for ln in rep["sections"][0]["lines"]] == ["I walk along the river"]


def test_a_bom_in_text_from_an_api_does_not_hide_the_tag():
    from ashugh.scan import scan

    rep = scan("﻿[Chorus]\nla la la\n")
    assert rep.units[0].section == "Chorus" and len(rep.lines) == 1


@pytest.mark.parametrize("lang,forbid", [("en", False), ("ru", False), ("hy", True)])
def test_spec_template_in_each_language(capsys, lang, forbid):
    main(["spec", "--lang", lang])
    out = capsys.readouterr().out
    assert f'language = "{lang}"' in out
    assert ('forbid_final = ["ը"]' in out) is forbid
    from ashugh.spec import loads

    loads(out)  # the template itself loads


def test_spec_from_a_song_has_no_leading_blank_line(tmp_path, capsys):
    song = tmp_path / "s.txt"
    song.write_text("the night\nis long\n\nso bright\nand strong\n", encoding="utf-8")
    main(["spec", "--from", str(song), "--keep", "syllables"])
    assert not capsys.readouterr().out.startswith("\n")


def test_fit_json_names_the_file(tmp_path, capsys):
    song = tmp_path / "s.txt"
    song.write_text("I walk along the river\n", encoding="utf-8")
    cands = tmp_path / "c.json"
    cands.write_text("{}", encoding="utf-8")
    main(["pick", str(song), "--candidates", str(cands), "--json"])
    assert json.loads(capsys.readouterr().out)["report"]["file"] == str(song)


@pytest.mark.parametrize(
    "rule,message",
    [
        ({"syllables": 0}, "syllables"),
        ({"syllables": -3}, "syllables"),
        ({"syllables": [8, 0]}, "syllables"),
        ({"meter": "iamb0"}, "feet"),
        ({"feet": 0}, "feet"),
    ],
)
def test_counts_must_be_positive(rule, message):
    from ashugh.spec import SpecError, from_dict

    with pytest.raises(SpecError, match=message):
        from_dict(rule)


def test_one_syllable_is_singular():
    from ashugh.scan import scan
    from ashugh.spec import from_dict

    rep = scan("I walk along the river\n", from_dict({"syllables": 1, "language": "en"}))
    assert any(i.message == "7 syllables, slot is 1" for i in rep.issues)
    rep = scan("night\n", from_dict({"syllables": 2, "language": "en"}))
    assert any(i.message == "1 syllable, slot is 2" for i in rep.issues)


@pytest.mark.parametrize("rows", [[{}], [{"task": "t"}], ["x"], {}])
def test_eval_report_refuses_malformed_rows(tmp_path, capsys, rows):
    results = tmp_path / "r.json"
    results.write_text(json.dumps({"rows": rows}), encoding="utf-8")
    assert main(["eval", "report", str(results)]) == 2
    assert "not an eval results file" in capsys.readouterr().err


def test_fit_without_an_api_key_is_an_error_not_a_traceback(tmp_path, capsys, monkeypatch):
    pytest.importorskip("anthropic")
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    song = tmp_path / "s.txt"
    song.write_text("I walk along the river\n", encoding="utf-8")
    assert main(["fit", str(song), "--syllables", "4"]) == 2
    err = capsys.readouterr().err
    assert "ANTHROPIC_API_KEY" in err and "Traceback" not in err


def test_messages_name_all_three_languages(capsys):
    from ashugh.scan import scan

    rep = scan("Καλημέρα κόσμε\n")
    (warn,) = [i for i in rep.issues if i.code == "script"]
    assert "Armenian, Russian or English" in warn.message
    assert rep.lines[0].fit.count == 6  # Ka-li-me-ra kos-me, by vowel groups
    with pytest.raises(SystemExit):
        main(["--help"])
    assert "Armenian, Russian and English" in capsys.readouterr().out
