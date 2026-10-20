import json
from pathlib import Path

import pytest

from ashugh import fit
from ashugh.cli import main
from ashugh.proposers import (
    CommandProposer,
    ProposerError,
    Request,
    StaticProposer,
    load_candidates,
)
from ashugh.spec import from_dict, load

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
SONG = (EXAMPLES / "song.hy.txt").read_text(encoding="utf-8")
SPEC = load(EXAMPLES / "song.hy.toml")


class Scripted:
    """A proposer that answers each round from a script and records requests."""

    name = "scripted"

    def __init__(self, rounds):
        self.rounds = list(rounds)
        self.calls: list[list[Request]] = []

    def propose(self, requests):
        self.calls.append(list(requests))
        answers = self.rounds.pop(0) if self.rounds else {}
        return {r.id: answers.get(r.line, []) for r in requests}


def test_nothing_to_fix_makes_no_requests():
    proposer = Scripted([])
    result = fit.fit_song("Мой дядя самых честных правил", from_dict({"syllables": 9}), proposer)
    assert result.ok and proposer.calls == [] and result.changes == []


def test_fixes_the_example_song():
    proposer = Scripted(
        [
            {
                3: ["Ու ես նորից սպասում եմ", "Ես նորից սպասում եմ քեզ"],
                9: ["Դու իմ երգն ես ու իմ վանք"],
                11: ["Դու իմ աշխարհն ես, իմ սեր"],
                14: ["Ու մնաց միայն իմ սիրտ", "Ու մնաց միայն սիրտս լուռ"],
            }
        ]
    )
    result = fit.fit_song(SONG, SPEC, proposer)
    assert result.ok, result.report.issues
    changed = {c.line: c.new for c in result.changes}
    assert changed[3] == "Ես նորից սպասում եմ քեզ"  # the rhyming one of the two
    assert changed[9] == "Դու իմ երգն ես ու իմ վանք"  # rhymes with կյանք
    assert 11 not in changed  # keeping կյանք is cheaper than losing it
    assert changed[14] == "Ու մնաց միայն սիրտս լուռ"  # the other one has 7 syllables
    assert "Ես նորից սպասում եմ քեզ" in result.text
    assert result.text.count("\n") == SONG.count("\n")


def test_requests_carry_the_constraints():
    proposer = Scripted([{}])
    fit.fit_song(SONG, SPEC, proposer, rounds=1)
    (requests,) = proposer.calls
    by_line = {r.line: r for r in requests}
    assert by_line[3].syllables == 8 and by_line[3].lang == "hy"
    assert any("9 syllables" in p for p in by_line[3].problems)
    assert by_line[14].avoid_final == ["ը"]
    assert set(by_line) >= {3, 9, 11, 14}


def test_infeasible_line_is_asked_again_with_what_failed():
    proposer = Scripted(
        [
            {2: ["Ու ես նորից ու նորից սպասում եմ քեզ"]},
            {2: ["Ես նորից սպասում եմ քեզ"]},
        ]
    )
    spec = from_dict({"syllables": 8, "language": "hy"})
    result = fit.fit_song("Գիշերն իջավ մեր քաղաքին\nՈւ ես նորից սպասում եմ քեզ", spec, proposer)
    assert result.ok
    second = {r.line: r for r in proposer.calls[1]}
    assert "Ու ես նորից ու նորից սպասում եմ քեզ" in second[2].rejected[0]
    assert result.rounds == 2


def test_broken_rhyme_asks_for_a_line_that_rhymes():
    proposer = Scripted(
        [{1: ["Я жду тебя опять"], 2: ["Ты где-то далеко"]}, {2: ["И не могу понять"]}]
    )
    spec = from_dict({"rhyme": "AA", "language": "ru"})
    result = fit.fit_song("Я жду тебя давно\nТы где-то далеко-далеко", spec, proposer)
    assert result.ok, result.report.issues
    retry = {r.line: r for r in proposer.calls[1]}
    assert retry and any(r.rhyme_with for r in retry.values())


def test_unresolved_lines_are_reported():
    proposer = Scripted([{}, {}])
    result = fit.fit_song(SONG, SPEC, proposer, rounds=2)
    assert not result.ok
    assert {u.line for u in result.unresolved} >= {3, 14}
    assert result.text == SONG


@pytest.mark.parametrize("bad", [None, 3, "", "two\nlines", "   ", {"text": 5}])
def test_garbage_candidates_are_ignored(bad):
    proposer = Scripted([{3: [bad, "Ես նորից սպասում եմ քեզ"]}])
    spec = from_dict({"syllables": 8, "language": "hy"})
    result = fit.fit_song("Գիշերն իջավ\nՈւ\nՈւ ես նորից սպասում եմ քեզ", spec, proposer, rounds=1)
    assert any(c.line == 3 for c in result.changes)


def test_a_failing_proposer_surfaces_as_an_error():
    class Broken:
        name = "broken"

        def propose(self, requests):
            raise ProposerError("model unavailable")

    with pytest.raises(ProposerError):
        fit.fit_song(SONG, SPEC, Broken())


def test_static_candidates_file(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"3": ["Ես նորից սպասում եմ քեզ"]}), encoding="utf-8")
    proposer = StaticProposer(load_candidates(path))
    assert proposer.propose([Request(id="L3", line=3, lang="hy", original="x")]) == {
        "L3": ["Ես նորից սպասում եմ քեզ"]
    }


@pytest.mark.parametrize(
    "content",
    ["not json", "[1, 2]", '{"x": ["a"]}', '{"3": "a"}', '{"3": [1]}', '[{"line": "3"}]'],
)
def test_bad_candidates_file_is_refused(tmp_path, content):
    path = tmp_path / "c.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ProposerError):
        load_candidates(path)


def test_candidates_file_accepts_a_list_of_objects(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps([{"line": 3, "candidates": ["a", "b"]}]), encoding="utf-8")
    assert load_candidates(path) == {3: ["a", "b"]}


def test_command_proposer_round_trip(tmp_path):
    script = tmp_path / "echo.py"
    script.write_text(
        "import json, sys\n"
        "reqs = json.load(sys.stdin)['requests']\n"
        "print(json.dumps({'lines': [{'id': r['id'], 'candidates': [r['original'] + '!']}"
        " for r in reqs]}))\n",
        encoding="utf-8",
    )
    import sys

    proposer = CommandProposer([sys.executable, str(script)])
    out = proposer.propose([Request(id="L1", line=1, lang="ru", original="Я жду")])
    assert out == {"L1": ["Я жду!"]}


@pytest.mark.parametrize(
    "body", ["print('nope')", "import sys; sys.exit(3)", "print('{\"lines\": 5}')"]
)
def test_command_proposer_failures(tmp_path, body):
    script = tmp_path / "bad.py"
    script.write_text(body + "\n", encoding="utf-8")
    import sys

    with pytest.raises(ProposerError):
        CommandProposer([sys.executable, str(script)]).propose(
            [Request(id="L1", line=1, lang="ru", original="Я жду")]
        )


def test_pick_cli(tmp_path, capsys):
    song = tmp_path / "s.txt"
    song.write_text(SONG, encoding="utf-8")
    cands = tmp_path / "c.json"
    cands.write_text(
        json.dumps(
            {
                "3": ["Ես նորից սպասում եմ քեզ"],
                "9": ["Դու իմ երգն ես ու իմ վանք"],
                "14": ["Ու մնաց միայն սիրտս լուռ"],
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "fixed.txt"
    spec = str(EXAMPLES / "song.hy.toml")
    code = main(["pick", str(song), "--spec", spec, "--candidates", str(cands), "-o", str(out)])
    assert code == 0, capsys.readouterr()
    assert "Ես նորից սպասում եմ քեզ" in out.read_text(encoding="utf-8")
    assert main(["scan", str(out), "--spec", spec]) == 0


def test_pick_cli_reports_unresolved(tmp_path, capsys):
    song = tmp_path / "s.txt"
    song.write_text(SONG, encoding="utf-8")
    cands = tmp_path / "c.json"
    cands.write_text("{}", encoding="utf-8")
    spec = str(EXAMPLES / "song.hy.toml")
    assert main(["pick", str(song), "--spec", spec, "--candidates", str(cands), "--json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is False and {u["line"] for u in data["unresolved"]} >= {3, 14}


def test_fit_cli_needs_a_proposer(tmp_path, capsys, monkeypatch):
    song = tmp_path / "s.txt"
    song.write_text(SONG, encoding="utf-8")
    monkeypatch.setenv("ASHUGH_PROPOSER", "")
    assert main(["fit", str(song), "--proposer", "nonsense"]) == 2


def test_replace_keeps_indent_line_endings_and_trailing_punctuation():
    text = "  Я жду,\r\nТы где?\n"
    out = fit.replace_lines(text, {1: "Я всё жду", 2: "Ты где же!"})
    assert out == "  Я всё жду,\r\nТы где же!\n"
    assert fit.replace_lines("a։\n", {1: "b"}) == "b։\n"
    assert fit.replace_lines("a\n", {5: "x"}) == "a\n"
