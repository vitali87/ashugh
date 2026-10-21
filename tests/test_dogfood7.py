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


def test_the_stressed_locative_of_chain_net_and_door():
    from ashugh.scan import scan

    text = "Сидит собака на цепи,\nПопалась рыбка нам в сети,\nВисит табличка на двери.\n"
    rep = scan(text, from_dict({"language": "ru", "meter": "iamb4", "rhyme": "AAA"}))
    assert rep.ok, [i.message for i in rep.issues]


@pytest.mark.parametrize("text, stress", [("на лету", 1), ("к лету", 0), ("в пылу", 1)])
def test_locatives_that_need_their_preposition(text, stress):
    from ashugh.scan import scan

    rep = scan(text + "\n", from_dict({"language": "ru"}))
    assert rep.lines[0].fit.stresses[1] == stress


def test_the_feminine_past_of_dozhdatsya():
    from ashugh.lang import ru

    assert ru.analyze_word("дождалась").readings[0].stress == 2  # дождала́сь


@pytest.mark.parametrize(
    "line, meter, stress",
    [
        ("Чуть слышно, кто-то, в двери постучал.", "iamb5", 0),  # в две́ри: into the doors
        ("Висит табличка на двери.", "iamb4", 1),
        ("Нет, нет, меня ты в сети не заманишь", "iamb5", 0),
    ],
)
def test_a_locative_noun_may_still_be_the_plural_after_v(line, meter, stress):
    from ashugh.scan import scan

    rep = scan(line + "\n", from_dict({"language": "ru", "meter": meter}))
    lr = rep.lines[0]
    i = next(k for k, w in enumerate(lr.line.words) if w.norm in ("двери", "сети"))
    assert rep.ok and lr.fit.stresses[i] == stress


def test_a_prefixed_feminine_past_may_keep_the_stem_stress_of_verse():
    from ashugh.scan import scan

    text = "Меня к тебе душа моя призвала,\nТы стала, словно светлое начало,\n"
    rep = scan(text, from_dict({"language": "ru", "meter": "iamb5", "rhyme": "AA"}))
    assert rep.ok  # призва́ла / нача́ло, as the poet has it


@pytest.mark.parametrize(
    "word, sung",
    [("ևս", "ե-վըս"), ("այլևս", "այ-լե-վըս"), ("դեռևս", "դե-ռե-վըս"), ("Այլևս", "Այ-լե-վըս")],
)
def test_evs_keeps_the_schwa_wiktionary_writes(word, sung):
    from ashugh.lang import hy

    w = hy.analyze_word(word)  # [jevəs], [ɑjlevəs], [derevəs]
    assert w.sung() == sung and w.readings[0].stress == w.size - 2


SONG = (
    "[Verse]\nThe harbor lights are burning low,\nThe boats are sleeping in the bay.\n\n"
    "[Chorus]\nOver the hills and away,\nFollow me home through the day.\n"
)


def test_a_sections_meter_does_not_inherit_the_feet_of_another():
    from ashugh.scan import scan
    from ashugh.spec import loads

    spec = loads('meter = "iamb4"\n[section.chorus]\nmeter = "dactyl"\n')
    rep = scan(SONG, spec)
    assert rep.ok, [i.message for i in rep.issues]


def test_a_section_that_names_its_feet_still_checks_them():
    from ashugh.scan import scan
    from ashugh.spec import loads

    spec = loads('meter = "iamb4"\n[section.chorus]\nmeter = "dactyl"\nfeet = [4]\n')
    rep = scan(SONG, spec)
    assert {i.code for i in rep.issues if i.severity == "error"} == {"feet"}


@pytest.mark.parametrize(
    "line, want",
    [
        ("Ո՞ւր ես, ո՞ւր, իմ ընկեր,", "Úr es, úr, im ənker?"),
        ("Արի՜, արի՜ մի գիշեր,", "Arí, arí mi gisher!"),
        ("Ինչո՞ւ ես լռում — ասա;", "Inchú es lərrum — asa?"),
        ("Ինչո՞ւ ես լռում (ասա),", "Inchú es lərrum (asa)?"),
        ("Ինչո՞ւ ես լռում, ասա»", "Inchú es lərrum, asa?»"),
        ("Ինչո՞ւ ես լռում, ասա…", "Inchú es lərrum, asa…?"),
    ],
)
def test_a_carried_question_mark_takes_the_place_of_a_comma(line, want):
    from unicodedata import normalize

    got = suno_text(line + "\n", armenian="latin", tags=False)
    assert normalize("NFC", got) == want + "\n"


def test_yev_is_a_vowel_to_suno():
    split = suno_text("Ու ես նայում եմ արև,\n", split="last", tags=False)
    assert "ա-րև" in split
    marked = suno_text("Արև՜, արև՜, մի՛ գնա,\n", armenian="schwa", tags=False)
    assert marked.count("՜") == 2


def test_the_too_long_hint_names_only_schwas_still_sung():
    from ashugh.scan import scan

    rep = scan("Սերն է իմ կյանքը\n", from_dict({"language": "hy", "syllables": 4}))
    (issue,) = [i for i in rep.issues if i.code == "syllables" and i.severity == "error"]
    assert "Սերն" not in issue.detail  # its ը is already left out of the 5


def test_the_sung_form_writes_the_unwritten_yo(capsys):
    assert main(["syl", "--lang", "ru", "мое твое лед еще идет Ее"]) == 0
    out = capsys.readouterr().out
    assert "мо-ё тво-ё лёд е-щё и-дёт Е-ё" in out


@pytest.mark.parametrize(
    "word, stress",
    [("отжила", 2), ("подзабыла", 2), ("отлюбовалась", 3), ("перепрятать", 2)],
)
def test_an_unknown_prefixed_verb_takes_its_bases_stress(word, stress):
    from ashugh.lang import ru

    w = ru.analyze_word(word)
    assert stress in w.stress_options() and not w.guessed


@pytest.mark.parametrize("word", ["западло", "усладила"])
def test_no_prefix_is_split_off_a_noun_or_with_one_letter(word):
    from ashugh.lang import ru

    assert ru.analyze_word(word).guessed


def test_no_possessive_exception_contradicts_wiktionary():
    from pathlib import Path

    from ashugh.lang.hy import NOT_POSSESSIVE

    data = Path(__file__).resolve().parent.parent / "eval" / "data" / "hye_armn_e_broad.tsv"
    ipa = dict(line.split("\t", 1) for line in data.read_text(encoding="utf-8").splitlines())
    wrong = [w for w in NOT_POSSESSIVE if w in ipa and ipa[w].rstrip().endswith(("ə s", "ə d"))]
    assert wrong == []
