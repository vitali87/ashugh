"""Bugs found by the seventh dogfooding round: translate, spec, suno, scan."""

import json

import pytest

from ashugh import fit
from ashugh.cli import main
from ashugh.proposers import StaticProposer
from ashugh.spec import from_dict


def test_translate_names_candidates_no_line_asked_for(tmp_path, capsys):
    song = tmp_path / "song.txt"
    song.write_text("[Verse]\nI wait for you all night\n", encoding="utf-8")
    cands = tmp_path / "c.json"
    cands.write_text(json.dumps({"1": ["Я жду тебя всю ночь"]}), encoding="utf-8")
    code = main(["translate", str(song), "--to", "ru", "--proposer", f"file:{cands}"])
    err = capsys.readouterr().err
    assert code == 1 and "line 1 is no lyric line" in err


def test_a_line_whose_candidates_are_all_malformed_says_why():
    spec = from_dict({"language": "en", "syllables": 4})
    text = "The night is very long\n"
    result = fit.fit_song(text, spec, StaticProposer({1: ["The night\nis long"]}), rounds=1)
    (u,) = result.unresolved
    assert u.reasons == ["no usable candidate: more than one line"]
    assert result.text == text  # never written into the song


def suno_text(text: str, **kw) -> str:
    from ashugh import suno

    return suno.format_song(text, **kw).text


def test_a_chorus_repeated_with_other_punctuation_or_yo_is_still_the_chorus():
    chorus = "Не плачь, не плачь, моя родная,\nВесна вернётся в этот дом.\n"
    last = chorus.replace("дом.", "дом!").replace("вернётся", "вернется")
    song = (
        "Я шёл по улице пустой,\nИ ветер пел о ней.\n\n" + chorus + "\n"
        "Прошла зима, пришла весна,\nИ снова ночь темна.\n\n" + last
    )
    tags = [ln for ln in suno_text(song).splitlines() if ln.startswith("[")]
    assert tags == ["[Verse 1]", "[Chorus]", "[Verse 2]", "[Chorus]"]


@pytest.mark.parametrize(
    "tag, key",
    [
        ("Финальный припев", "chorus"),
        ("Последний припев", "chorus"),
        ("Второй куплет", "verse"),
        ("Վերջին կրկներգ", "chorus"),
        ("Երկրորդ տուն", "verse"),
    ],
)
def test_russian_and_armenian_ordinals_name_the_same_section(tag, key):
    from ashugh.lyrics import section_key

    assert section_key(tag) == key


@pytest.mark.parametrize(
    "tag, suno_tag",
    [
        ("[Припев (женский вокал)]", "[Chorus (женский вокал)]"),
        ("[Куплет 1 (тихо)]", "[Verse 1 (тихо)]"),
        ("[Կրկներգ (x2)]", "[Chorus x2]"),
        ("[Припев (х3)]", "[Chorus x3]"),
        ("[Финальный припев]", "[Final Chorus]"),
        ("[Второй куплет]", "[Verse 2]"),
        ("[Վերջին կրկներգ]", "[Final Chorus]"),
        ("[Bridge: softly]", "[Bridge: softly]"),
        ("[Мой раздел]", "[Мой раздел]"),  # not a section Suno knows: left as written
    ],
)
def test_suno_names_tags_with_notes_and_ordinals(tag, suno_tag):
    assert suno_text(f"{tag}\nЯ жду\n").splitlines()[0] == suno_tag


def test_a_translation_carries_suno_tags_not_the_source_languages():
    from ashugh import translate

    source = "[Куплет 1]\nЯ жду тебя всю ночь\n\n[Припев]\nИ мне нельзя помочь\n"
    proposer = StaticProposer({2: ["I wait for you all night"], 5: ["Until the morning light"]})
    result = translate.translate_song(source, "en", proposer, keep={"syllables"}, rounds=1)
    assert [ln for ln in result.text.splitlines() if ln.startswith("[")] == [
        "[Verse 1]",
        "[Chorus]",
    ]


def test_spec_from_warns_that_a_line_with_digits_sets_a_short_slot(tmp_path, capsys):
    song = tmp_path / "song.txt"
    song.write_text("Սպասում եմ 3 տարի,\nԵս քեզ եմ սպասում։\n", encoding="utf-8")
    assert main(["spec", "--from", str(song)]) == 0
    captured = capsys.readouterr()
    assert "syllables = [6, 6]" in captured.out
    assert "L1" in captured.err and "digits" in captured.err


def test_translate_warns_that_a_source_line_with_digits_sets_a_short_slot():
    from ashugh import translate

    source = "Seventeen summers and 2 broken hearts\n"
    proposer = StaticProposer({1: ["Семнадцать лет и два разбитых сердца"]})
    result = translate.translate_song(source, "ru", proposer, keep={"syllables"}, rounds=1)
    assert any("L1" in w and "digits" in w for w in result.warnings)
    assert "warnings" in result.as_dict()


def test_mcp_derive_spec_names_a_line_with_digits():
    from ashugh import mcp

    reply = mcp.Server().handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "derive_spec", "arguments": {"lyrics": "I wait 4 you\n"}},
        }
    )
    assert reply is not None
    data = json.loads(reply["result"]["content"][0]["text"])
    assert data["warnings"] and "digits" in data["warnings"][0]
