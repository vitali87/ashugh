import json
from pathlib import Path

import pytest

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
    rep = scan("Вихри снежные кракозябрами", from_dict({"meter": "trochee"}), lang="ru")
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


def test_rhyme_resolves_an_ambiguous_stress_at_the_line_end():
    rep = scan("Плывут по небу облака\nЛетят они издалека", lang="ru")
    first = rep.lines[0]
    assert first.fit.stresses[3] == 2  # облака́, the stress that rhymes with издалека́
    assert rep.units[0].scheme == "AA"


def test_rhyme_does_not_override_the_meter():
    spec = from_dict({"meter": "iamb", "language": "ru"})
    rep = scan("Висит на двери замок\nИ в нём звенит звонок", spec)
    assert rep.lines[0].fit.stresses[3] == 0  # за́мок keeps the iamb; замо́к would rhyme


def test_forced_stress_in_the_meter():
    from ashugh import meter

    words = scan("Плывут по небу облака", lang="ru").lines[0].line.words
    assert meter.fit(words, "iamb", force={3: 0}).stresses[3] == 0
    assert meter.fit(words, "iamb", force={3: 2}).stresses[3] == 2
    assert meter.fit(words, "iamb", force={3: 7}).stresses[3] in (0, 2)  # impossible: ignored


def test_second_locative_scans_in_meter():
    rep = scan("Что кинул он в краю родном", from_dict({"meter": "iamb4"}), lang="ru")
    assert rep.ok


def codes(rep):
    return [i.code for i in rep.issues if i.severity == "error"]


def test_wrong_number_of_feet_is_an_error_even_when_stresses_are_clean():
    rep = scan("Я жду тебя у окон", from_dict({"meter": "iamb4"}), lang="ru")
    assert codes(rep) == ["feet"]
    assert scan("Я жду тебя у старых окон", from_dict({"meter": "iamb4"}), lang="ru").ok


def test_english_initial_inversion_is_allowed():
    rep = scan("Sometime too hot the eye of heaven shines", from_dict({"meter": "iamb5"}))
    assert rep.ok


def test_inversion_only_at_the_start_of_an_english_line():
    rep = scan("The night was a summer in the hall", from_dict({"meter": "iamb4"}))
    assert "meter" in codes(rep)
    rep = scan("Белая ночь пришла ко мне", from_dict({"meter": "iamb4"}), lang="ru")
    assert "meter" in codes(rep), "a Russian iamb may not start on a stressed polysyllable"


def test_english_compound_may_shift_its_stress_onto_the_second_part():
    rep = scan("And every fair from fair sometime declines", from_dict({"meter": "iamb5"}))
    assert rep.ok


def test_long_word_stress_does_not_shift_backwards():
    # in-for-MA-tion keeps its primary stress: the secondary before it does not take over
    rep = scan("I want the information now", from_dict({"meter": "trochee4"}))
    assert "meter" in codes(rep)


def test_english_line_may_end_on_a_promoted_syllable():
    rep = scan("Thou art more lovely and more temperate", from_dict({"meter": "iamb5"}))
    assert rep.ok
    rep = scan("Thou art more lovely and more temperate", from_dict({"meter": "iamb4"}))
    assert rep.ok, "or as four feet with a dactylic ending"


def test_english_promoted_beat_can_carry_the_rhyme():
    text = "I keep the summer in my memory\nAnd every road will set me free\n"
    rep = scan(text, from_dict({"meter": "iamb", "rhyme": "AA"}))
    assert rep.ok
    assert rep.lines[0].fit.promoted


def test_promotion_does_not_make_any_dactyl_rhyme():
    text = "I keep the summer in my memory\nAnd every road will lead me home\n"
    rep = scan(text, from_dict({"meter": "iamb", "rhyme": "AA"}))
    assert "rhyme" in codes(rep)


def test_syl_cli_takes_meter_names_with_feet(capsys):
    assert main(["syl", "--meter", "iamb4", "Я помню чудное мгновенье"]) == 0
    assert "9" in capsys.readouterr().out
    assert main(["syl", "--meter", "sonnet", "Я помню"]) == 2


def test_neither_of_us_has_seven_syllables():
    assert scan("Neither of us wants to go", from_dict({"syllables": 7})).ok


@pytest.mark.parametrize(
    "a,b",
    [
        ("So sing my love of ships gone by", "The lighthouse burns against the sky"),
        ("Salty hair and sunburned skin", "Let the final wave roll in"),
    ],
)
def test_english_line_final_particle_takes_the_stress_and_the_rhyme(a, b):
    assert scan(f"{a}\n{b}\n", from_dict({"rhyme": "AA"})).ok


def test_line_final_particle_in_meter():
    assert scan("So sing my love of ships gone by", from_dict({"meter": "iamb4"})).ok


def test_poetic_plural_of_year_scans_and_rhymes():
    text = "Проходят года и года\nНо я прихожу как всегда\n"
    assert scan(text, from_dict({"meter": "amphibrach3", "rhyme": "AA"}), lang="ru").ok


@pytest.mark.parametrize(
    "text,lang,count",
    [
        ("Ճիվ-ճիվ-ճիվ-ճիվ ճռվողում", "hy", 7),
        ("Բուրդ ունեն փափուկ-փափուկ", "hy", 7),
        ("Тихо-тихо падает снег", "ru", 8),
    ],
)
def test_reduplications_are_separate_words(text, lang, count):
    rep = scan(text, from_dict({"syllables": count}), lang=lang)
    assert rep.lines[0].fit.count == count
    assert len(rep.lines[0].line.words) > len(text.split())


def test_hyphenated_compounds_stay_one_word():
    rep = scan("Кто-то из-за угла", from_dict({}), lang="ru")
    assert [w.norm for w in rep.lines[0].line.words] == ["кто-то", "из-за", "угла"]


def test_reduplication_stress_fits_a_trochee():
    rep = scan("Բուրդ ունեն փափուկ-փափուկ", from_dict({"meter": "trochee4"}), lang="hy")
    assert rep.ok


def test_a_pronoun_may_sit_on_a_weak_beat():
    spec = from_dict({"meter": "anapest3"})
    assert scan("Вспоминай эту ночь легкокрылую", spec, lang="ru").ok
    assert scan("И согрей ею душу остылую", spec, lang="ru").ok
    assert not scan("Вспоминай дорогу легкокрылую", spec, lang="ru").ok


@pytest.mark.parametrize(
    "a,b",
    [
        ("Where have you been", "under the sun"),
        ("I know we can", "under the summer sun"),
        ("I know it was", "the way it does"),
        ("Tell me what it's for", "I was waiting for her"),
    ],
)
def test_reduced_function_word_forms_do_not_rhyme(a, b):
    rep = scan(f"{a}\n{b}\n", from_dict({"language": "en", "rhyme": "AA"}))
    assert "rhyme" in codes(rep)


@pytest.mark.parametrize(
    "text,spec",
    [
        ("I keep the summer in my memory\nAnd every road will set me free\n", {"meter": "iamb4"}),
        (
            "I keep the summer in my memory\nAnd every road will set me free\n",
            {"meter": "iamb", "endings": "dm"},
        ),
        ("плывут куда-то облака\nпришла издалека\n", {"language": "ru", "meter": "iamb3"}),
    ],
)
def test_rhyme_never_buys_a_new_line_error(text, spec):
    assert "feet" not in codes(scan(text, from_dict(spec)))
    assert "ending" not in codes(scan(text, from_dict(spec)))


@pytest.mark.parametrize(
    "a,b",
    [("Поставь эту книгу на полку", "Не будет от этого толку")],
)
def test_accusative_after_na_is_not_a_locative(a, b):
    assert scan(f"{a}\n{b}\n", from_dict({"rhyme": "AA"}), lang="ru").ok


def test_idiom_v_vidu_is_not_end_stressed():
    rep = scan("Только имей в виду\nя к тебе не приду\n", from_dict({"rhyme": "AA"}), lang="ru")
    assert "rhyme" in codes(rep)


@pytest.mark.parametrize(
    "text,lang",
    [("О-о-о\nО-о-о\n", "ru"), ("Где же ты, моя любовь, о-о-о\nЯ тебя зову, о-о-о\n", "ru")],
)
def test_vocalise_refrains_still_rhyme(text, lang):
    assert scan(text, from_dict({"rhyme": "AA"}), lang=lang).ok


def test_line_final_secondary_stress_counts_as_a_foot():
    rep = scan("I saw a butterfly", from_dict({"meter": "iamb2"}))
    assert "feet" in codes(rep)
    assert scan("I saw a butterfly", from_dict({"meter": "iamb3"})).ok


def test_dolnik_feet_follow_the_asked_count():
    assert scan("Я иду по тёмной улице", from_dict({"meter": "dolnik3"}), lang="ru").ok


@pytest.mark.parametrize(
    "a,b", [("Я люблю тебя еще", "Не люблю тебя вообще"), ("Снова дождь идет", "А тебя всё нет")]
)
def test_modern_yo_does_not_rhyme_with_e(a, b):
    assert "rhyme" in codes(scan(f"{a}\n{b}\n", from_dict({"rhyme": "AA"}), lang="ru"))


def test_cyrillic_repeat_marker():
    from ashugh.lyrics import section_key

    assert section_key("Припев х2") == "chorus"
    assert section_key("Chorus ×2") == "chorus"


def test_promote_on_a_line_without_english_is_harmless():
    from ashugh import meter
    from ashugh.lang import analyze
    from ashugh.lyrics import tokenize

    words = analyze("ru", tokenize("Мой дядя самых честных правил"), {})
    assert meter.fit(words, "iamb", promote=True).count == 9


def test_stress_may_move_onto_a_preposition():
    spec = from_dict({"meter": "trochee4"})
    assert scan("Ходит по сердцу тревога", spec, lang="ru").ok  # по́ сердцу
    assert scan("Мама за руку берёт", spec, lang="ru").ok  # за́ руку
    rep = scan("Ходит по дому тревога", spec, lang="ru")
    assert "meter" in codes(rep), "по до́му is not a listed shift"


def test_preposition_stress_is_optional():
    assert scan("Пойдём гулять по лесу мы", from_dict({"meter": "iamb4"}), lang="ru").ok


def test_shifted_line_end_rhymes_on_the_preposition():
    rep = scan("Мама ведёт меня за руку", from_dict({"meter": "dactyl3"}), lang="ru")
    assert rep.ok
    (tail,) = rep.lines[0].tails
    assert tail.word == "за руку" and tail.vowel == "a" and tail.post == 2


def test_noun_alone_keeps_its_stress():
    from ashugh.lang import analyze
    from ashugh.lyrics import tokenize

    (w,) = analyze("ru", tokenize("сердцу"), {})
    assert None not in w.stress_options()
    words = analyze("ru", tokenize("по сердцу"), {})
    assert None in words[1].stress_options() and not words[1].ambiguous


def test_elision_note_speaks_the_lines_language():
    rep = scan("I still recall our wondrous meeting", from_dict({"syllables": 9}))
    notes = [i.message for i in rep.issues if i.code == "syllables"]
    assert notes and all("ը" not in m for m in notes)
