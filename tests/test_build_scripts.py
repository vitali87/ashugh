import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_ru_lexicon as ru_build  # noqa: E402


@pytest.mark.parametrize(
    "infinitive,expected",
    [
        ("звуча'ть", ["звуча'л", "звуча'ла", "звуча'ло", "звуча'ли"]),
        ("ду'маться", ["ду'мался", "ду'малась", "ду'малось", "ду'мались"]),
        (
            "сформули'ровать",
            ["сформули'ровал", "сформули'ровала", "сформули'ровало", "сформули'ровали"],
        ),
    ],
)
def test_past_forms_follow_the_infinitive(infinitive, expected):
    assert ru_build.past_forms(infinitive) == expected


@pytest.mark.parametrize(
    "infinitive",
    [
        "производиться",  # no stress mark: nothing to copy
        "вести'сь",  # -сти: the past stem is not the infinitive's
        "мочь",
        "пусть",
        "",
    ],
)
def test_past_forms_refused_where_they_cannot_be_derived(infinitive):
    assert ru_build.past_forms(infinitive) == []


def test_build_fills_missing_past_forms(tmp_path):
    header = ["bare", "accented", "aspect", "past_m", "past_f", "past_n", "past_pl", "presfut_sg1"]
    rows = [
        ["звучать", "звуча'ть", "imperfective", "", "", "", "", "звучу'"],
        ["жить", "жить", "imperfective", "жи'л", "жила'", "жи'ло", "жи'ли", "живу'"],
    ]
    (tmp_path / "verbs.csv").write_text(
        "\n".join("\t".join(r) for r in [header, *rows]) + "\n", encoding="utf-8"
    )
    for name in ("nouns.csv", "adjectives.csv", "others.csv"):
        (tmp_path / name).write_text("bare\taccented\n", encoding="utf-8")
    table = ru_build.build(tmp_path)
    assert table["звучал"] == [2] and table["звучали"] == [2]
    assert table["жила"] == [2], "listed forms are kept as they are"
    assert "жил" not in table, "monosyllables are still left out"


def test_a_headwords_own_stress_comes_first(tmp_path):
    header = ["bare", "accented", "sg_nom", "sg_gen"]
    rows = [["вод", "вод", "вод", "во'да"], ["вода", "вода'", "вода'", "воды'"]]
    (tmp_path / "nouns.csv").write_text(
        "\n".join("\t".join(r) for r in [header, *rows]) + "\n", encoding="utf-8"
    )
    for name in ("verbs.csv", "adjectives.csv", "others.csv"):
        (tmp_path / name).write_text("bare\taccented\n", encoding="utf-8")
    table = ru_build.build(tmp_path)
    assert table["вода"] == [2, 1]  # вода́, the noun, before во́да of вод


def test_a_prefixed_verb_ends_its_feminine_past_like_its_base(tmp_path):
    header = ["bare", "accented", "aspect", "past_m", "past_f", "past_n", "past_pl", "presfut_sg1"]
    rows = [
        ["звать", "звать", "imperfective", "зва'л", "звала'", "зва'ло", "зва'ли", "зову'"],
        ["позвать", "позва'ть", "perfective", "позва'л", "позва'ла", "", "", "позову'"],
        ["вызвать", "вы'звать", "perfective", "вы'звал", "вы'звала", "", "", "вы'зову"],
        ["ждать", "ждать", "imperfective", "жда'л", "ждала'", "жда'ло", "жда'ли", "жду'"],
        ["дождаться", "дожда'ться", "perfective", "дожда'лся", "дожда'лась", "", "", "дожду'сь"],
        ["рвать", "рвать", "imperfective", "рва'л", "рвала'", "рва'ло", "рва'ли", "рву'"],
        ["прорвать", "прорва'ть", "perfective", "", "", "", "", ""],
        ["мести", "мести'", "imperfective", "мёл", "мела'", "мело'", "мели'", "мету'"],
        ["замести", "замести'", "perfective", "замёл", "заме'ла", "", "", "замету'"],
        ["быть", "быть", "imperfective", "бы'л", "была'", "бы'ло", "бы'ли", "бу'ду"],
        ["забыть", "забы'ть", "perfective", "забы'л", "забы'ла", "", "", "забу'ду"],
        ["знать", "знать", "imperfective", "зна'л", "зна'ла", "зна'ло", "зна'ли", "зна'ю"],
        ["узнать", "узна'ть", "perfective", "узна'л", "узна'ла", "", "", "узна'ю"],
        ["пить", "пить", "imperfective", "пи'л", "пила'", "пи'ло", "пи'ли", "пью'"],
        ["вопить", "вопи'ть", "imperfective", "вопи'л", "вопи'ла", "", "", "воплю'"],
        ["родить", "роди'ть", "perfective", "роди'л", "родила'", "", "", "рожу'"],
        ["породить", "породи'ть", "perfective", "породи'л", "породи'ла", "", "", "порожу'"],
        ["стричь", "стричь", "imperfective", "стри'г", "стригла'", "", "", "стригу'"],
        ["остричь", "остри'чь", "perfective", "остри'г", "остри'гла", "", "", "остригу'"],
    ]
    (tmp_path / "verbs.csv").write_text(
        "\n".join("\t".join(r) for r in [header, *rows]) + "\n", encoding="utf-8"
    )
    for name in ("nouns.csv", "adjectives.csv", "others.csv"):
        (tmp_path / name).write_text("bare\taccented\n", encoding="utf-8")
    table = ru_build.build(tmp_path)
    # позвала́ first, the norm; позва́ла kept, which verse and speech use too
    assert table["позвала"] == [3, 2] and table["позвал"] == [2]
    assert table["дождалась"] == [3, 2] and table["прорвала"] == [3, 2]
    assert table["замела"] == [3, 2]
    assert table["вызвала"] == [1], "вы- keeps the stress: вы́звала"
    assert table["забыла"] == [2], "забы́ла, unlike была́"
    assert table["узнала"] == [2], "a base stressed on its stem changes nothing"
    assert table["вопила"] == [2], "вопить is no во- with пить: воплю, not вопью"
    assert table["породила"] == [3] and table["остригла"] == [2], "роди́ла, стри́гла"


def test_an_obsolete_word_lends_no_stress_to_a_common_one(tmp_path):
    header = ["bare", "accented", "sg_nom", "sg_prep", "pl_nom"]
    rows = [
        ["стена", "стена'", "стена'", "стене'", "сте'ны"],
        ["стен", "сте'н", "сте'н", "сте'не", "сте'ны"],  # the sthene, a unit no one sings
    ]
    (tmp_path / "nouns.csv").write_text(
        "\n".join("\t".join(r) for r in [header, *rows]) + "\n", encoding="utf-8"
    )
    for name in ("verbs.csv", "adjectives.csv", "others.csv"):
        (tmp_path / name).write_text("bare\taccented\n", encoding="utf-8")
    assert ru_build.build(tmp_path)["стене"] == [2]
