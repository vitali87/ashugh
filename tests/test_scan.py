import json
from pathlib import Path

from ashugh import lyrics, report
from ashugh.cli import main
from ashugh.scan import scan
from ashugh.spec import from_dict, load

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def issues(rep, severity="error"):
    return [(i.line, i.code) for i in rep.issues if i.severity == severity]


def test_armenian_example_finds_the_three_faults():
    rep = scan(
        (EXAMPLES / "song.hy.txt").read_text(encoding="utf-8"),
        load(EXAMPLES / "song.hy.toml"),
    )
    assert issues(rep) == [(3, "syllables"), (11, "rhyme"), (14, "final")]
    by_code = {i.code: i for i in rep.issues}
    assert "ըս-պա-սում" in by_code["syllables"].detail
    assert "«սիրտ» / «կյանք»" in by_code["rhyme"].detail


def test_russian_example():
    rep = scan(
        (EXAMPLES / "song.ru.txt").read_text(encoding="utf-8"),
        load(EXAMPLES / "song.ru.toml"),
    )
    assert issues(rep) == [
        (4, "rhyme"),
        (5, "feet"),
        (5, "meter"),
        (10, "feet"),
        (10, "meter"),
        (10, "rhyme"),
    ]
    assert (8, "stress") in issues(rep, "info")  # замок read as за́мок


def test_sections_and_stanzas():
    text = "[Verse 1]\nодин\nдва\n\nтри\n[Chorus x2]\n(ooh)\nчетыре\n"
    ls = lyrics.parse(text)
    assert [(ln.number, ln.key, ln.unit, ln.index) for ln in ls] == [
        (2, "verse", 0, 0),
        (3, "verse", 0, 1),
        (5, "verse", 1, 0),
        (8, "chorus", 2, 0),
    ]


def test_parentheses_are_backing_vocals():
    assert lyrics.tokenize("Я жду (я жду) тебя") == ["Я", "жду", "тебя"]


def test_lexicon_fixes_a_line():
    text = "Ու ես կայսրություն եմ ուզում"
    plain = scan(text, from_dict({"syllables": 9}))
    fixed = scan(text, from_dict({"syllables": 9, "lexicon": {"կայսրություն": "կայ-սը-րու-թյուն"}}))
    assert not plain.ok and fixed.ok


def test_unknown_stress_is_a_warning():
    rep = scan("Вихри снежные крутя", from_dict({"meter": "trochee"}), lang="ru")
    assert (1, "stress") in issues(rep, "warning")


def test_json_report_shape():
    rep = scan("Я помню чудное мгновенье", from_dict({"meter": "iamb4", "syllables": 9}))
    data = json.loads(report.as_json(rep))
    assert data["ok"] is True
    (line,) = data["sections"][0]["lines"]
    assert line["syllables"] == 9 and line["feet"] == 4 and line["grid"] == "x/x/xxx/x"
    assert line["words"][3]["syllables"] == ["мгно", "ве", "нье"]


def test_cli_exit_codes(capsys, tmp_path):
    lyr = tmp_path / "a.txt"
    lyr.write_text("Ու ես նորից սպասում եմ քեզ\n", encoding="utf-8")
    assert main(["scan", str(lyr), "--syllables", "9"]) == 0
    assert main(["scan", str(lyr), "--syllables", "8"]) == 1
    out = capsys.readouterr().out
    assert "9 syllables, slot is 8" in out and "ըս-պա-սում" in out
    assert main(["scan", str(lyr), "--meter", "hexameter"]) == 2


def test_cli_syl_and_rhyme(capsys):
    assert main(["syl", "Մկրտիչ", "սպասել"]) == 0
    assert "Մը-կըր-տի́չ ըս-պա-սե́լ" in capsys.readouterr().out
    assert main(["rhyme", "сердце", "дверце"]) == 0
    assert main(["rhyme", "սիրտ", "կյանք"]) == 1
