import json

import pytest

from ashugh import lyrics, suno
from ashugh.cli import main
from ashugh.spec import from_dict


def fmt(text, **kw):
    kw.setdefault("tags", False)
    return suno.format_song(text, **kw).text


def test_marks_only_ambiguous_russian_stress():
    out = fmt("Не уходи, мой тёплый замок", spec=from_dict({"meter": "iamb"}))
    assert out == "Не уходи, мой тёплый зАмок"


def test_acute_marks():
    out = fmt("Не уходи, мой тёплый замок", spec=from_dict({"meter": "iamb"}), stress="acute")
    assert out == "Не уходи, мой тёплый за́мок"


def test_no_marks():
    out = fmt("Не уходи, мой тёплый замок", spec=from_dict({"meter": "iamb"}), stress="none")
    assert out == "Не уходи, мой тёплый замок"


def test_restores_certain_yo_and_leaves_doubtful_ones():
    assert fmt("Еще одна ночь") == "Ещё одна ночь"
    assert fmt("Это все") == "Это все"


def test_keeps_case_and_punctuation():
    out = fmt("ЕЩЕ, еще!", stress="none")
    assert out == "ЕЩЁ, ещё!"


def test_backing_vocals_are_left_alone():
    assert fmt("Я жду (еще) тебя", stress="none") == "Я жду (еще) тебя"


def test_armenian_schwas_written_out():
    out = fmt("Ես քեզ եմ սպասում,\nՄկրտիչն էլ է սպասում", armenian="schwa")
    assert out == "Ես քեզ եմ ըսպասում,\nՄըկըրտիչն էլ է ըսպասում"


def test_armenian_capital_on_schwa():
    assert fmt("Սպասել", armenian="schwa") == "Ըսպասել"


@pytest.mark.parametrize(
    "src,latin",
    [
        ("Ես քեզ եմ սպասում", "Yes kez em əspasum"),
        ("Մկրտիչ", "Məkərtich"),
        ("Երևան", "Yerevan"),
        ("Շնորհակալություն", "Shənorhakalutyun"),
        ("կյանք ու սեր", "kyank u ser"),
        ("որ", "vor"),
        ("ժամ, ղողանջ, ռազմիկ", "zham, ghoghanj, rrazmik"),
    ],
)
def test_armenian_romanization(src, latin):
    assert fmt(src, armenian="latin") == latin


def test_romanization_schwa_letter():
    assert fmt("Մկրտիչ", armenian="latin", schwa="e") == "Mekertich"


@pytest.mark.parametrize(
    "tag,want",
    [
        ("[Куплет 1]", "[Verse 1]"),
        ("[Припев]", "[Chorus]"),
        ("[Կրկներգ]", "[Chorus]"),
        ("[Տուն 2]", "[Verse 2]"),
        ("[Бридж]", "[Bridge]"),
        ("[Вступление]", "[Intro]"),
        ("[pre-chorus]", "[Pre-Chorus]"),
        ("[Solo]", "[Solo]"),
    ],
)
def test_tags_are_normalized(tag, want):
    assert fmt(f"{tag}\nЯ жду", tags=True) == f"{want}\nЯ жду"


def test_untagged_song_gets_verse_and_chorus_tags():
    song = (
        "Я жду тебя\nВ ночи\n\nПриди ко мне\nПриди\n\nТы далеко\nМолчишь\n\nПриди ко мне\nПриди\n"
    )
    out = fmt(song, stress="none", tags=True)
    assert out.splitlines()[0] == "[Verse 1]"
    tags = [ln for ln in out.splitlines() if ln.startswith("[")]
    assert tags == ["[Verse 1]", "[Chorus]", "[Verse 2]", "[Chorus]"]


def test_single_stanza_untagged_gets_a_verse_tag():
    assert fmt("Я жду", stress="none", tags=True) == "[Verse]\nЯ жду"


def test_tags_can_be_left_alone():
    assert suno.format_song("Я жду", stress="none", tags=False).text == "Я жду"


def test_split_last_word_for_held_notes():
    out = fmt("Мой дядя самых честных правил", split="last", stress="none", tags=False)
    assert out == "Мой дядя самых честных пра-вил"


def test_split_all():
    out = fmt("Ես քեզ սպասում", split="all", armenian="schwa", tags=False)
    assert out == "Ես քեզ ըս-պա-սում"


def test_notes_list_the_changes():
    result = suno.format_song("Еще один замок", spec=from_dict({"meter": "dolnik"}))
    kinds = {n.kind for n in result.notes}
    assert "yo" in kinds


@pytest.mark.parametrize(
    "kw", [{"stress": "bold"}, {"armenian": "cyrillic"}, {"split": "some"}, {"schwa": ""}]
)
def test_bad_options(kw):
    with pytest.raises(ValueError):
        suno.format_song("Я жду", **kw)


def test_empty_text():
    assert fmt("", tags=False) == ""


def test_token_spans_cover_tokens_outside_parentheses():
    spans = lyrics.token_spans("Я (не) жду, ты-то")
    assert [t for _, _, t in spans] == ["Я", "жду", "ты-то"]
    text = "Я (не) жду, ты-то"
    assert all(text[a:b] == t for a, b, t in spans)


def test_policy_chooses_spelling_per_word():
    policy = {"hy": {"default": "script", "words": {"սպասում": "latin"}}}
    out = fmt("Ես քեզ եմ սպասում", policy=policy)
    assert out == "Ես քեզ եմ əspasum"


def test_suno_cli(tmp_path, capsys):
    song = tmp_path / "s.txt"
    song.write_text("[Припев]\nНе уходи, мой тёплый замок\n", encoding="utf-8")
    assert main(["suno", str(song), "--meter", "iamb"]) == 0
    assert capsys.readouterr().out == "[Chorus]\nНе уходи, мой тёплый зАмок\n"
    policy = tmp_path / "p.json"
    policy.write_text("not json", encoding="utf-8")
    assert main(["suno", str(song), "--policy", str(policy)]) == 2
    policy.write_text(json.dumps({"hy": {"default": "klingon"}}), encoding="utf-8")
    assert main(["suno", str(song), "--policy", str(policy)]) == 2


def test_russian_policy_picks_the_stress_marks():
    spec = from_dict({"meter": "iamb"})
    out = fmt("Не уходи, мой тёплый замок", spec=spec, policy={"ru": {"default": "acute"}})
    assert out == "Не уходи, мой тёплый за́мок"
    with pytest.raises(ValueError):
        fmt("Я жду", policy={"ru": {"default": "bold"}})


@pytest.mark.parametrize("stress", ["caps", "acute", "none"])
def test_stress_marks_the_user_wrote_are_kept(stress):
    from ashugh.model import ACUTE

    word = "за" + ACUTE + "мок"
    out = fmt(f"Мой тёплый {word}", stress=stress)
    want = {"caps": "зАмок", "acute": word, "none": word}[stress]
    assert out == f"Мой тёплый {want}"
    other = fmt("Мой тёплый замо" + ACUTE + "к", stress="caps")
    assert other == "Мой тёплый замОк"


def test_russian_policy_per_word():
    spec = from_dict({"meter": "iamb"})
    policy = {"ru": {"default": "plain", "words": {"замок": "caps"}}}
    out = fmt("Не уходи, мой тёплый замок", spec=spec, policy=policy)
    assert out == "Не уходи, мой тёплый зАмок"
    policy = {"ru": {"default": "caps", "words": {"замок": "plain"}}}
    assert fmt("Не уходи, мой тёплый замок", spec=spec, policy=policy).endswith("замок")


@pytest.mark.parametrize(
    "tag,want",
    [
        ("[Припев x2]", "[Chorus x2]"),
        ("[Припев 2x]", "[Chorus 2x]"),
        ("[Կրկներգ x3]", "[Chorus x3]"),
        ("[Куплет 2]", "[Verse 2]"),
        ("[Chorus x2]", "[Chorus x2]"),
    ],
)
def test_repeat_counts_survive_tag_translation(tag, want):
    assert fmt(f"{tag}\nЯ жду", tags=True) == f"{want}\nЯ жду"


def test_line_separator_is_not_a_line_break():
    text = "Мой тёплый замок\u2028ещё\nНе уходи"
    out = fmt(text, stress="none")
    assert out.split("\n")[1] == "Не уходи"


def test_yo_is_still_restored_where_verse_may_read_e():
    assert fmt("В томленьях грусти безнадежной", stress="none") == "В томленьях грусти безнадёжной"
