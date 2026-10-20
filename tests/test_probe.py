import json
import sys
from pathlib import Path

import pytest

from ashugh import probe
from ashugh.cli import main


def test_make_probes_renders_each_mode():
    plan = probe.make_probes(["սպասել", "Մկրտիչ"], "hy")
    assert len(plan) == 6
    by = {(p.word, p.mode): p for p in plan}
    assert "սպասել" in by[("սպասել", "script")].lyrics
    assert "ըսպասել" in by[("սպասել", "schwa")].lyrics
    assert "əspasel" in by[("սպասել", "latin")].lyrics
    assert by[("Մկրտիչ", "latin")].sung == "մը-կըր-տիչ"
    assert by[("Մկրտիչ", "latin")].syllables == 3
    assert by[("Մկրտիչ", "latin")].lyrics.startswith("[Verse]\n")
    assert len({p.id for p in plan}) == 6


def test_make_probes_russian_marks():
    plan = probe.make_probes(["замОк"], "ru")
    modes = {p.mode: p for p in plan}
    assert set(modes) == {"plain", "caps", "acute"}
    assert "замок" in modes["plain"].lyrics and "замОк" in modes["caps"].lyrics
    assert "замо́к" in modes["acute"].lyrics


@pytest.mark.parametrize("words,lang", [([], "hy"), (["սպասել"], "fr"), (["", " "], "hy")])
def test_make_probes_refuses(words, lang):
    with pytest.raises(ValueError):
        probe.make_probes(words, lang)


def test_custom_modes():
    plan = probe.make_probes(["սպասել"], "hy", modes=["latin"])
    assert [p.mode for p in plan] == ["latin"]
    with pytest.raises(ValueError):
        probe.make_probes(["սպասել"], "hy", modes=["opera"])


def scripted_transcripts(plan, good, bad="ապասել"):
    out = {}
    for p in plan:
        word = good if p.mode != "latin" else bad
        out[p.id] = f"{word}, {word}, {word}"
    return out


def test_score_prefers_the_mode_whisper_hears_right():
    plan = probe.make_probes(["սպասել"], "hy")
    transcripts = scripted_transcripts(plan, "սպասել")
    result = probe.score(plan, transcripts)
    assert result.policy["hy"]["default"] in ("script", "schwa")
    assert result.scores["սպասել"]["latin"] < result.scores["սպասել"]["script"]
    assert result.missing == []


def test_per_word_override_when_a_word_disagrees():
    plan = probe.make_probes(["սպասել", "Մկրտիչ"], "hy")
    transcripts = {}
    for p in plan:
        if p.word == "սպասել":
            transcripts[p.id] = "սպասել" if p.mode == "script" else "պաս"
        else:
            transcripts[p.id] = "Մկրտիչ" if p.mode == "latin" else "կիրթ"
    result = probe.score(plan, transcripts)
    assert result.policy["hy"]["words"] == {"մկրտիչ": "latin"} or result.policy["hy"]["words"] == {
        "սպասել": "script"
    }


def test_missing_transcripts_are_listed():
    plan = probe.make_probes(["սպասել"], "hy")
    first = plan[0]
    result = probe.score(plan, {first.id: "սպասել"})
    assert sorted(result.missing) == sorted(p.id for p in plan[1:])


def test_score_needs_some_transcripts():
    plan = probe.make_probes(["սպասել"], "hy")
    with pytest.raises(ValueError):
        probe.score(plan, {})


def test_plan_round_trip(tmp_path):
    plan = probe.make_probes(["սպասել"], "hy")
    path = tmp_path / "plan.json"
    probe.save_plan(plan, path)
    assert probe.load_plan(path) == plan


@pytest.mark.parametrize("content", ["nope", "{}", '[{"id": 1}]'])
def test_bad_plan(tmp_path, content):
    path = tmp_path / "plan.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        probe.load_plan(path)


def test_transcripts_from_a_directory(tmp_path):
    (tmp_path / "hy-000-script.txt").write_text("սպասել\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("ignored", encoding="utf-8")
    assert probe.load_transcripts(tmp_path) == {"hy-000-script": "սպասել"}


@pytest.mark.parametrize("content", ["nope", "[1]", '{"a": 1}'])
def test_bad_transcripts(tmp_path, content):
    path = tmp_path / "t.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        probe.load_transcripts(path)


def test_transcribe_without_whisper(tmp_path, monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "whisper", None)
    with pytest.raises(probe.ProbeError):
        probe.transcribe(tmp_path, [], model="tiny")


def test_probe_cli(tmp_path, capsys):
    plan = tmp_path / "plan.json"
    lyrics_dir = tmp_path / "lyrics"
    assert (
        main(
            [
                "probe",
                "make",
                "սպասել",
                "--lang",
                "hy",
                "-o",
                str(plan),
                "--lyrics",
                str(lyrics_dir),
            ]
        )
        == 0
    )
    files = sorted(p.name for p in lyrics_dir.iterdir())
    assert len(files) == 3 and all(f.endswith(".txt") for f in files)
    entries = json.loads(plan.read_text(encoding="utf-8"))
    transcripts = tmp_path / "t.json"
    transcripts.write_text(
        json.dumps({e["id"]: "սպասել" for e in entries}, ensure_ascii=False), encoding="utf-8"
    )
    policy = tmp_path / "policy.json"
    assert main(["probe", "score", str(plan), str(transcripts), "-o", str(policy)]) == 0
    data = json.loads(policy.read_text(encoding="utf-8"))
    assert data["hy"]["default"] in ("script", "schwa", "latin")
    assert main(["suno", str(lyrics_dir / files[0]), "--policy", str(policy)]) == 0


def test_a_reduplication_can_be_probed():
    from ashugh import probe

    assert probe.make_probes(["тихо-тихо"], "ru")


@pytest.mark.parametrize("bad", ["два слова", "", "…"])
def test_a_probe_is_one_word(bad):
    from ashugh import probe

    with pytest.raises(ValueError, match="word"):
        probe.make_probes([bad], "ru")


class FakeWhisper:
    """Stands in for openai-whisper: load_model(name).transcribe(path, language=...)."""

    def __init__(self, heard):
        self.heard, self.loaded, self.calls = heard, [], []

    def load_model(self, name):
        self.loaded.append(name)
        return self

    def transcribe(self, path, language=None):
        self.calls.append((Path(path).name, language))
        return {"text": " " + self.heard[Path(path).stem] + " "}


def heard_like_suno(plan):
    """What a listener might hear: the schwa spelling sung right, the others garbled."""
    return {p.id: (p.word if p.mode == "schwa" else "սպել") for p in plan}


def test_transcribe_with_whisper_end_to_end(tmp_path, monkeypatch):
    plan = probe.make_probes(["սպասել"], "hy")
    clips = tmp_path / "clips"
    clips.mkdir()
    for k, p in enumerate(plan):
        (clips / f"{p.id}{['.mp3', '.wav', '.m4a'][k % 3]}").write_bytes(b"audio")
    fake = FakeWhisper(heard_like_suno(plan))
    monkeypatch.setitem(sys.modules, "whisper", fake)
    transcripts = probe.transcribe(clips, plan, model="tiny")
    assert fake.loaded == ["tiny"] and {lang for _, lang in fake.calls} == {"hy"}
    assert set(transcripts) == {p.id for p in plan}
    result = probe.score(plan, transcripts)
    assert result.policy["hy"]["default"] == "schwa"


def test_transcribe_skips_missing_clips(tmp_path, monkeypatch):
    plan = probe.make_probes(["սպասել"], "hy")
    (tmp_path / f"{plan[0].id}.mp3").write_bytes(b"audio")
    monkeypatch.setitem(sys.modules, "whisper", FakeWhisper(heard_like_suno(plan)))
    assert list(probe.transcribe(tmp_path, plan)) == [plan[0].id]


def write_engine(tmp_path, body):
    script = tmp_path / "asr.py"
    script.write_text(body, encoding="utf-8")
    return f"cmd:{sys.executable} {script} {{audio}} {{lang}}"


def test_transcribe_with_a_command(tmp_path):
    plan = probe.make_probes(["замок"], "ru")
    for p in plan:
        (tmp_path / f"{p.id}.wav").write_bytes(p.word.encode("utf-8"))
    engine = write_engine(
        tmp_path,
        "import sys\nprint(open(sys.argv[1], encoding='utf-8').read().split()[0], sys.argv[2])\n",
    )
    transcripts = probe.transcribe(tmp_path, plan, engine=engine)
    assert set(transcripts) == {p.id for p in plan}
    assert all(t.endswith(" ru") for t in transcripts.values())


@pytest.mark.parametrize(
    "body,message",
    [("import sys\nsys.exit(3)\n", "exited 3"), ("print('')\n", "nothing")],
)
def test_transcribe_command_failures(tmp_path, body, message):
    plan = probe.make_probes(["замок"], "ru")
    (tmp_path / f"{plan[0].id}.wav").write_bytes(b"x")
    with pytest.raises(probe.ProbeError, match=message):
        probe.transcribe(tmp_path, plan, engine=write_engine(tmp_path, body))


def test_unknown_engine(tmp_path):
    with pytest.raises(probe.ProbeError, match="engine"):
        probe.transcribe(tmp_path, [], engine="sphinx")


def test_probe_pipeline_cli(tmp_path, capsys):
    plan_path = tmp_path / "probes.json"
    assert main(["probe", "make", "սպասել", "--lang", "hy", "-o", str(plan_path)]) == 0
    plan = probe.load_plan(plan_path)
    clips = tmp_path / "clips"
    clips.mkdir()
    heard = heard_like_suno(plan)
    for p in plan:
        (clips / f"{p.id}.wav").write_text(heard[p.id], encoding="utf-8")
    engine = write_engine(
        tmp_path, "import sys\nprint(open(sys.argv[1], encoding='utf-8').read())\n"
    )
    out = tmp_path / "transcripts.json"
    args = ["probe", "transcribe", str(clips), "--plan", str(plan_path), "--engine", engine]
    assert main([*args, "-o", str(out)]) == 0
    policy = tmp_path / "policy.json"
    assert main(["probe", "score", str(plan_path), str(out), "-o", str(policy)]) == 0
    song = tmp_path / "song.txt"
    song.write_text("Ես սպասել եմ քեզ\n", encoding="utf-8")
    capsys.readouterr()
    assert main(["suno", str(song), "--policy", str(policy), "--no-tags"]) == 0
    assert "ըսպասել" in capsys.readouterr().out
