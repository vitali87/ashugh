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
    rows = [["водь", "водь", "водь", "во'да"], ["вода", "вода'", "вода'", "воды'"]]
    (tmp_path / "nouns.csv").write_text(
        "\n".join("\t".join(r) for r in [header, *rows]) + "\n", encoding="utf-8"
    )
    for name in ("verbs.csv", "adjectives.csv", "others.csv"):
        (tmp_path / name).write_text("bare\taccented\n", encoding="utf-8")
    table = ru_build.build(tmp_path)
    assert table["вода"] == [2, 1]  # вода́, the noun, before во́да of a genitive


def _two_files(tmp_path, nouns=(), verbs=(), header=("bare", "accented", "sg_nom", "sg_gen")):
    (tmp_path / "nouns.csv").write_text(
        "\n".join("\t".join(r) for r in [header, *nouns]) + "\n", encoding="utf-8"
    )
    (tmp_path / "verbs.csv").write_text(
        "\n".join("\t".join(r) for r in [("bare", "accented"), *verbs]) + "\n", encoding="utf-8"
    )
    for name in ("adjectives.csv", "others.csv"):
        (tmp_path / name).write_text("bare\taccented\n", encoding="utf-8")


def test_the_word_far_more_frequent_comes_first(tmp_path):
    # the dump lists words in order of frequency: писа́ть is row 2, пи́сать row 200
    filler = [[f"слово{k}", f"сло'во{k}"] for k in range(197)]
    _two_files(tmp_path, verbs=[["писать", "писа'ть"], *filler, ["писать", "пи'сать"]])
    assert ru_build.build(tmp_path)["писать"] == [2, 1]


def test_a_close_call_of_frequency_keeps_the_vowel_order(tmp_path):
    filler = [[f"слово{k}", f"сло'во{k}"] for k in range(5)]
    _two_files(tmp_path, verbs=[["писать", "писа'ть"], *filler, ["писать", "пи'сать"]])
    assert ru_build.build(tmp_path)["писать"] == [1, 2]


def test_an_obsolete_or_dropped_row_gives_no_reading(tmp_path):
    rows = [["вода", "вода'", "вода'", "воды'"], ["вод", "вод", "вод", "во'да"]]
    rows.append(["ужин", "ужи'н", "ужи'н", "ужи'на"])
    rows.append(["ужин", "у'жин", "у'жин", "у'жина"])
    _two_files(tmp_path, nouns=rows)
    table = ru_build.build(tmp_path)
    assert table["вода"] == [2] and table["ужин"] == [1]


def test_a_commoner_yo_twin_is_read_first_and_a_rare_one_not_at_all():
    rows = {"моем": 1336, "моём": 8, "небо": 95, "нёбо": 10**6, "черта": 185, "чёрта": 449}
    twins = ru_build.yo_twins(rows)
    assert twins == {("моем", "моём"): "+", ("небо", "нёбо"): "-"}


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


def _dump(tmp_path, **files):
    for name in ("nouns.csv", "verbs.csv", "adjectives.csv", "others.csv"):
        header, rows = files.get(name.removesuffix(".csv"), (["bare", "accented"], []))
        (tmp_path / name).write_text(
            "\n".join("\t".join(r) for r in [header, *rows]) + "\n", encoding="utf-8"
        )


def test_build_derives_the_forms_the_dump_leaves_out(tmp_path):
    adjectives = (
        ["bare", "accented", "comparative", "short_f", "decl_m_gen", "decl_pl_gen"],
        [
            ["прежний", "пре'жний", "", "", "", ""],
            ["нежный", "не'жный", "", "нежна'", "не'жного", "не'жных"],
            ["крепкий", "кре'пкий", "", "крепка'", "кре'пкого", "кре'пких"],
        ],
    )
    verbs = (
        ["bare", "accented", "past_m", "presfut_sg1", "presfut_sg2"],
        [
            ["бросить", "бро'сить", "бро'сил", "бро'шу", "бро'сишь"],
            ["стать", "стать", "ста'л", "ста'ну", "ста'нешь"],
        ],
    )
    nouns = (
        ["bare", "accented", "gender", "sg_nom", "sg_gen"],
        [["вселенная", "вселе'нная", "f", "", ""]],
    )
    others = (["bare", "accented"], [["людской", "людско'й"]])
    _dump(tmp_path, adjectives=adjectives, verbs=verbs, nouns=nouns, others=others)
    listed = ru_build.build(tmp_path)
    table = ru_build.extra(tmp_path, listed)
    assert "прежнему" not in listed, "derived forms go to their own table"
    assert "нежного" in listed and "нежного" not in table
    assert table["прежнему"] == [1]
    assert table["нежнее"] == [2] and table["понежнее"] == [3]
    assert table["крепче"] == [1] and table["покрепче"] == [2]
    assert table["брошен"] == [1] and table["брошенных"] == [1]
    assert table["ставший"] == [1]
    assert table["вселенной"] == [2]
    assert table["людских"] == [2]
    assert table["подольше"] == [2], "irregular comparatives with по-"
    assert "крепкее" not in table


def test_a_derived_form_never_overrules_a_listed_one(tmp_path):
    adjectives = (
        ["bare", "accented", "comparative", "short_f"],
        [["узкий", "у'зкий", "", "узка'"]],
    )
    others = (["bare", "accented"], [["уже", "уже'"]])
    _dump(tmp_path, adjectives=adjectives, others=others)
    listed = ru_build.build(tmp_path)
    assert listed["уже"] == [2], "уже́ (already) stays as the dump has it"
    assert "уже" not in ru_build.extra(tmp_path, listed)


def test_a_derived_yo_form_does_not_shadow_a_listed_e_form(tmp_path):
    adjectives = (["bare", "accented", "short_m"], [["нужный", "ну'жный", "ну'жен"]])
    verbs = (
        ["bare", "accented", "past_m", "presfut_sg1", "presfut_sg2"],
        [["нудить", "нуди'ть", "нуди'л", "нужу'", "нуди'шь"]],
    )
    _dump(tmp_path, adjectives=adjectives, verbs=verbs)
    listed = ru_build.build(tmp_path)
    made = ru_build.extra(tmp_path, listed)
    assert listed["нужен"] == [1]
    assert "нужён" not in made
    assert "нужённый" in made, "the rest of the participle stays"


@pytest.mark.parametrize(
    "form,positions",
    [
        ("трёхэта'жный", {3}),
        ("надё'жный", {2}),
        ("ёлка", {1}),
        ("чёрно-бе'лый", {1, 3}),
        ("го'ссекретарём", {5}),
        ("такс'иста", {2}),  # a mark the dump put before its vowel
    ],
)
def test_a_compound_yo_beside_a_marked_stress_is_not_a_reading(form, positions):
    assert ru_build.stress_positions(form)[1] == positions


def test_stresses_are_ranked_by_how_usual_their_form_is(tmp_path):
    nouns = (
        ["bare", "accented", "sg_nom", "sg_gen", "sg_dat", "pl_nom"],
        [
            ["глаз", "глаз", "глаз", "гла'за", "", "глаза'"],
            ["поле", "по'ле", "по'ле", "по'ля", "по'лю", "поля'"],
        ],
    )
    verbs = (
        ["bare", "accented", "past_m", "presfut_sg1"],
        [["полоть", "поло'ть", "поло'л", "полю'"]],
    )
    _dump(tmp_path, nouns=nouns, verbs=verbs)
    marked = ru_build.ranked(tmp_path)
    assert [p for p, _ in marked["глаза"]] == [2, 1], "the plural before the genitive"
    assert ru_build.encode(marked["полю"]) == "2v1", "the verb's stress is marked"
    assert ru_build.encode(marked["глаза"]) == "2p1", "the plural's stress is marked"


def test_an_infinitive_is_a_verb_form_no_preposition_takes(tmp_path):
    header = ["bare", "accented", "aspect", "past_m", "presfut_sg1"]
    rows = [["вести", "вести'", "imperfective", "вёл", "веду'"]]
    (tmp_path / "verbs.csv").write_text(
        "\n".join("\t".join(r) for r in [header, *rows]) + "\n", encoding="utf-8"
    )
    (tmp_path / "nouns.csv").write_text(
        "bare\taccented\tsg_nom\tsg_gen\nвесть\tве'сть\tве'сть\tве'сти\n", encoding="utf-8"
    )
    for name in ("adjectives.csv", "others.csv"):
        (tmp_path / name).write_text("bare\taccented\n", encoding="utf-8")
    table = ru_build.ranked(tmp_path)
    assert (2, "v") in table["вести"], "вести́, the infinitive: no reading after без"
    assert (1, "") in table["вести"], "ве́сти, of весть"
