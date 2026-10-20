import json
import sys

import pytest

from ashugh import translate
from ashugh.cli import main
from ashugh.scan import scan
from ashugh.spec import SpecError, dumps, from_dict, loads

ONEGIN = (
    "[Verse]\nМой дядя самых честных правил,\nКогда не в шутку занемог,\n"
    "Он уважать себя заставил\nИ лучше выдумать не мог.\n"
)
COUPLET = "I wait for you all night\nuntil the morning light\n"


class Scripted:
    name = "scripted"

    def __init__(self, rounds):
        self.rounds = list(rounds)
        self.calls = []

    def propose(self, requests):
        self.calls.append(list(requests))
        answers = self.rounds.pop(0) if self.rounds else {}
        return {r.id: answers.get(r.line, []) for r in requests}


def test_grid_of_a_russian_stanza():
    data = translate.derive_spec(scan(ONEGIN), keep={"syllables", "meter", "rhyme", "endings"})
    stanza = data["stanza"]["1"]
    assert stanza == {
        "syllables": [9, 8, 9, 8],
        "meter": "iamb",
        "feet": [4, 4, 4, 4],
        "rhyme": "ABAB",
        "endings": "fmfm",
    }


def test_keep_limits_what_is_copied():
    data = translate.derive_spec(scan(ONEGIN), keep={"syllables"})
    assert data["stanza"]["1"] == {"syllables": [9, 8, 9, 8]}


def test_unrhymed_lines_become_free():
    data = translate.derive_spec(
        scan("one two three\nfour five six\nseven eight\n"), keep={"rhyme"}
    )
    assert "rhyme" not in data["stanza"]["1"]
    data = translate.derive_spec(scan("the night\nis long\nso bright\n"), keep={"rhyme"})
    assert data["stanza"]["1"]["rhyme"] == "A-A"


@pytest.mark.parametrize("bad", [{"rhythm"}, {"syllables", "melody"}])
def test_unknown_keep_is_refused(bad):
    with pytest.raises(ValueError):
        translate.derive_spec(scan(ONEGIN), keep=bad)


def test_spec_toml_round_trip():
    data = translate.derive_spec(scan(ONEGIN), keep={"syllables", "meter", "rhyme", "endings"})
    data["language"] = "hy"
    text = dumps(data)
    spec = loads(text)
    rule = spec.rule_for("verse", 0)
    assert rule.syllables == (9, 8, 9, 8) and rule.meter == "iamb" and rule.rhyme == "ABAB"
    assert spec.language == "hy"


def test_stanza_rules_override_sections():
    spec = from_dict(
        {"syllables": 8, "section": {"verse": {"syllables": 7}}, "stanza": {"2": {"syllables": 5}}}
    )
    assert spec.rule_for("verse", 0).syllables == (7,)
    assert spec.rule_for("verse", 1).syllables == (5,)
    assert spec.rule_for("chorus", 1).syllables == (5,)
    assert spec.rule_for("chorus", 0).syllables == (8,)


@pytest.mark.parametrize("bad", [{"stanza": {"x": {}}}, {"stanza": {"0": {}}}, {"stanza": 3}])
def test_bad_stanza_tables(bad):
    with pytest.raises(SpecError):
        from_dict(bad)


def test_translates_a_couplet_keeping_count_and_rhyme():
    proposer = Scripted(
        [{1: ["Я жду тебя всю ночь"], 2: ["До самого утра", "И мне нельзя помочь"]}]
    )
    result = translate.translate_song(COUPLET, "ru", proposer, keep={"syllables", "rhyme"})
    assert result.ok, result.report.issues
    assert result.text == "Я жду тебя всю ночь\nИ мне нельзя помочь\n"
    (requests,) = proposer.calls
    first = {r.line: r for r in requests}
    assert first[1].source == "I wait for you all night" and first[1].source_lang == "en"
    assert first[1].original == "" and first[1].lang == "ru" and first[1].syllables == 6
    assert first[1].rhyme_with == []  # never the source language's rhyme words


def test_second_round_asks_for_the_partner_rhyme():
    proposer = Scripted(
        [
            {1: ["Я жду тебя всю ночь"], 2: ["До самого утра"]},
            {2: ["И мне нельзя помочь"]},
        ]
    )
    result = translate.translate_song(COUPLET, "ru", proposer, keep={"syllables", "rhyme"})
    assert result.ok and result.rounds == 2
    retry = {r.line: r for r in proposer.calls[1]}
    assert "ночь" in retry[2].rhyme_with[0] or "ночь" in retry.get(1, retry[2]).rhyme_with[0]


def test_unresolved_translation_keeps_the_best_attempt():
    proposer = Scripted(
        [{1: ["Я жду тебя всю ночь"], 2: ["Слишком длинная строка для этого места"]}]
    )
    result = translate.translate_song(
        COUPLET, "ru", proposer, keep={"syllables", "rhyme"}, rounds=1
    )
    assert not result.ok
    assert {u.line for u in result.unresolved} >= {2}
    assert "Я жду тебя всю ночь" in result.text


def test_unknown_target_language():
    with pytest.raises(ValueError):
        translate.translate_song(COUPLET, "fr", Scripted([]))


def test_empty_source():
    with pytest.raises(ValueError):
        translate.translate_song("[Verse]\n\n", "ru", Scripted([]))


def test_spec_from_cli(tmp_path, capsys):
    src = tmp_path / "onegin.txt"
    src.write_text(ONEGIN, encoding="utf-8")
    assert main(["spec", "--from", str(src), "--keep", "syllables,rhyme", "--lang", "hy"]) == 0
    spec = loads(capsys.readouterr().out)
    assert spec.language == "hy" and spec.rule_for("verse", 0).syllables == (9, 8, 9, 8)
    assert main(["spec", "--from", str(src), "--keep", "tempo"]) == 2


def test_translate_cli_with_a_command_proposer(tmp_path, capsys):
    src = tmp_path / "en.txt"
    src.write_text(COUPLET, encoding="utf-8")
    script = tmp_path / "llm.py"
    answers = {"L1": ["Я жду тебя всю ночь"], "L2": ["И мне нельзя помочь"]}
    script.write_text(
        "import json, sys\n"
        f"answers = {json.dumps(answers, ensure_ascii=False)!r}\n"
        "answers = json.loads(answers)\n"
        "reqs = json.load(sys.stdin)['requests']\n"
        "print(json.dumps({'lines': [{'id': r['id'], 'candidates': answers.get(r['id'], [])}"
        " for r in reqs]}, ensure_ascii=False))\n",
        encoding="utf-8",
    )
    out = tmp_path / "ru.txt"
    code = main(
        [
            "translate",
            str(src),
            "--to",
            "ru",
            "--proposer",
            f"cmd:{sys.executable} {script}",
            "-o",
            str(out),
        ]
    )
    assert code == 0, capsys.readouterr()
    assert out.read_text(encoding="utf-8") == "Я жду тебя всю ночь\nИ мне нельзя помочь\n"


def test_unresolved_translation_keeps_a_dashed_attempt_whole():
    proposer = Scripted([{1: ["Я жду тебя — а ты молчишь всю ночь"], 2: ["До самого утра"]}])
    result = translate.translate_song(
        COUPLET, "ru", proposer, keep={"syllables", "rhyme"}, rounds=1
    )
    assert "Я жду тебя — а ты молчишь всю ночь" in result.text


def test_translation_does_not_carry_the_source_full_stop():
    source = "Ես սպասում եմ քեզ։\nՄինչև առավոտ։\n"
    proposer = Scripted([{1: ["Я жду тебя всю ночь"], 2: ["До самого утра"]}])
    result = translate.translate_song(source, "ru", proposer, keep={"syllables"}, rounds=1)
    assert "։" not in result.text
