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
