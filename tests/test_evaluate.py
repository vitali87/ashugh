import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from ashugh import evaluate
from ashugh.cli import main

TASKS = Path(__file__).resolve().parent.parent / "eval" / "tasks"


def write_task(folder, name="t1", **over):
    data = {
        "id": name,
        "language": "hy",
        "prompt": "A short song about waiting at night.",
        "spec": {"syllables": 8, "rhyme": "ABAB", "forbid_final": ["ը"]},
    }
    data.update(over)
    lines = [
        f'id = "{data["id"]}"',
        f'language = "{data["language"]}"',
        f'prompt = "{data["prompt"]}"',
        "",
        "[spec]",
    ]
    for k, v in data["spec"].items():
        lines.append(f"{k} = {json.dumps(v, ensure_ascii=False)}")
    path = folder / f"{name}.toml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


DRAFT = (
    "[Verse 1]\nԳիշերն իջավ մեր քաղաքին,\nՈւ ես նորից սպասում եմ քեզ,\n"
    "Լուսինը շողաց տանիքին,\nՈւ քամին նորից կանչեց մեզ։\n"
)


class Scripted:
    name = "scripted"

    def __init__(self, answers):
        self.answers = answers

    def propose(self, requests):
        return {r.id: self.answers.get(r.line, []) for r in requests}


def test_bundled_tasks_load():
    tasks = evaluate.load_tasks(TASKS)
    assert len(tasks) >= 10
    assert {t.language for t in tasks} == {"hy", "ru", "en"}
    assert len({t.id for t in tasks}) == len(tasks)
    for t in tasks:
        assert t.spec.language == t.language and not t.spec.empty


@pytest.mark.parametrize(
    "over,message",
    [
        ({"language": "fr"}, "language"),
        ({"prompt": ""}, "prompt"),
        ({"spec": {"colour": 1}}, "unknown key"),
    ],
)
def test_bad_tasks_are_refused(tmp_path, over, message):
    write_task(tmp_path, **over)
    with pytest.raises(ValueError, match=message):
        evaluate.load_tasks(tmp_path)


def test_duplicate_ids_are_refused(tmp_path):
    write_task(tmp_path, "a", id="same")
    write_task(tmp_path, "b", id="same")
    with pytest.raises(ValueError, match="duplicate"):
        evaluate.load_tasks(tmp_path)


def test_describe_spec_in_words(tmp_path):
    (task,) = evaluate.load_tasks(write_task(tmp_path))
    text = evaluate.describe(task.spec)
    assert "8 sung syllables" in text and "ABAB" in text and "ը" in text


def test_run_alone_and_with_ashugh(tmp_path):
    write_task(tmp_path)
    drafts = tmp_path / "drafts"
    drafts.mkdir()
    (drafts / "t1.txt").write_text(DRAFT, encoding="utf-8")
    tasks = evaluate.load_tasks(tmp_path)
    proposer = Scripted({3: ["Ես նորից սպասում եմ քեզ"]})
    rows = evaluate.run(tasks, evaluate.DirWriter(drafts), ["alone", "ashugh"], proposer)
    by_mode = {r["mode"]: r for r in rows}
    assert by_mode["alone"]["line_pass_rate"] == 0.75 and by_mode["alone"]["song_ok"] is False
    assert by_mode["ashugh"]["line_pass_rate"] == 1.0 and by_mode["ashugh"]["song_ok"] is True
    assert by_mode["ashugh"]["changes"] == 1
    summary = evaluate.summarize(rows)
    assert summary["alone"]["line_pass_rate"] == 0.75 and summary["ashugh"]["songs_ok"] == 1.0


def test_missing_draft_is_recorded_not_fatal(tmp_path):
    write_task(tmp_path)
    rows = evaluate.run(
        evaluate.load_tasks(tmp_path), evaluate.DirWriter(tmp_path / "none"), ["alone"]
    )
    assert rows[0]["error"] and rows[0]["line_pass_rate"] == 0.0


def test_ashugh_mode_needs_a_proposer(tmp_path):
    write_task(tmp_path)
    with pytest.raises(ValueError):
        evaluate.run(evaluate.load_tasks(tmp_path), evaluate.DirWriter(tmp_path), ["ashugh"], None)


def test_unknown_mode(tmp_path):
    write_task(tmp_path)
    with pytest.raises(ValueError):
        evaluate.run(evaluate.load_tasks(tmp_path), evaluate.DirWriter(tmp_path), ["solo"])


def test_command_writer(tmp_path):
    script = tmp_path / "w.py"
    script.write_text(
        "import json, sys\ntask = json.load(sys.stdin)\nprint('Я жду ' + task['id'])\n",
        encoding="utf-8",
    )
    writer = evaluate.CommandWriter([sys.executable, str(script)])
    write_task(tmp_path)
    (task,) = evaluate.load_tasks(tmp_path)
    assert writer.write(task).strip() == "Я жду t1"


def test_claude_writer_request_shape(tmp_path):
    write_task(tmp_path)
    (task,) = evaluate.load_tasks(tmp_path)
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            stop_reason="end_turn", content=[SimpleNamespace(type="text", text="[Verse]\nԵս\n")]
        )

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    text = evaluate.ClaudeWriter(client=client).write(task)
    assert text == "[Verse]\nԵս\n"
    (call,) = calls
    assert call["model"] == "claude-opus-5-5" and call["fallbacks"] == "default"
    assert "8 sung syllables" in call["messages"][0]["content"]


def test_eval_cli(tmp_path, capsys):
    write_task(tmp_path)
    drafts = tmp_path / "drafts"
    drafts.mkdir()
    (drafts / "t1.txt").write_text(DRAFT, encoding="utf-8")
    out = tmp_path / "results.json"
    code = main(
        [
            "eval",
            "run",
            str(tmp_path),
            "--writer",
            f"dir:{drafts}",
            "--modes",
            "alone",
            "-o",
            str(out),
        ]
    )
    assert code == 0
    assert "alone" in capsys.readouterr().out
    assert json.loads(out.read_text(encoding="utf-8"))["summary"]["alone"]["tasks"] == 1
    assert main(["eval", "report", str(out)]) == 0
    assert main(["eval", "run", str(tmp_path), "--writer", "gpt"]) == 2


def test_agent_round_trip(tmp_path):
    write_task(tmp_path)
    drafts = tmp_path / "drafts"
    drafts.mkdir()
    (drafts / "t1.txt").write_text(DRAFT, encoding="utf-8")
    tasks = evaluate.load_tasks(tmp_path)
    exported = evaluate.export_requests(tasks, drafts)
    assert [r["line"] for r in exported["t1"]["requests"]] == [3]
    out = tmp_path / "round1"
    rows = evaluate.apply_candidates(tasks, drafts, {"t1": {"3": ["Ես նորից սպասում եմ քեզ"]}}, out)
    assert rows[0]["changes"] == 1
    fixed = (out / "t1.txt").read_text(encoding="utf-8")
    assert "Ես նորից սպասում եմ քեզ" in fixed
    assert evaluate.export_requests(tasks, out) == {}


def test_apply_without_candidates_copies_the_draft(tmp_path):
    write_task(tmp_path)
    drafts = tmp_path / "drafts"
    drafts.mkdir()
    (drafts / "t1.txt").write_text(DRAFT, encoding="utf-8")
    out = tmp_path / "round1"
    evaluate.apply_candidates(evaluate.load_tasks(tmp_path), drafts, {}, out)
    assert (out / "t1.txt").read_text(encoding="utf-8") == DRAFT


def test_apply_refuses_bad_candidates(tmp_path):
    write_task(tmp_path)
    drafts = tmp_path / "drafts"
    drafts.mkdir()
    (drafts / "t1.txt").write_text(DRAFT, encoding="utf-8")
    with pytest.raises(ValueError):
        evaluate.apply_candidates(
            evaluate.load_tasks(tmp_path), drafts, {"t1": {"x": ["a"]}}, tmp_path / "o"
        )


def test_eval_requests_and_apply_cli(tmp_path, capsys):
    write_task(tmp_path)
    drafts = tmp_path / "drafts"
    drafts.mkdir()
    (drafts / "t1.txt").write_text(DRAFT, encoding="utf-8")
    req = tmp_path / "req.json"
    assert main(["eval", "requests", str(tmp_path), "--drafts", str(drafts), "-o", str(req)]) == 0
    assert "t1" in json.loads(req.read_text(encoding="utf-8"))
    cands = tmp_path / "c.json"
    cands.write_text(
        json.dumps({"t1": {"3": ["Ես նորից սպասում եմ քեզ"]}}, ensure_ascii=False), encoding="utf-8"
    )
    out = tmp_path / "r1"
    assert (
        main(
            [
                "eval",
                "apply",
                str(tmp_path),
                "--drafts",
                str(drafts),
                "--candidates",
                str(cands),
                "--out",
                str(out),
            ]
        )
        == 0
    )
    assert (out / "t1.txt").exists()


def test_describe_alternating_feet(tmp_path):
    (task,) = evaluate.load_tasks(
        write_task(tmp_path, language="en", spec={"meter": "iamb", "feet": [4, 3]})
    )
    assert "iamb with 4, 3 stressed beats per line, in turn" in evaluate.describe(task.spec)
