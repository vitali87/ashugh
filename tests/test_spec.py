import pytest

from ashugh.spec import SpecError, from_dict, load, template


def test_sections_inherit_and_override():
    spec = from_dict(
        {
            "syllables": 8,
            "rhyme": "ABAB",
            "section": {"chorus": {"syllables": [7, 7, 7, 5], "rhyme": "AABB"}},
        }
    )
    verse, chorus = spec.rule_for("verse"), spec.rule_for("chorus")
    assert verse.syllables_at(5) == 8
    assert [chorus.syllables_at(i) for i in range(5)] == [7, 7, 7, 5, 7]
    assert chorus.rhyme == "AABB"


def test_meter_with_feet():
    rule = from_dict({"meter": "trochee4"}).base
    assert rule.meter == "trochee" and rule.feet_at(0) == 4


def test_rhyme_groups_repeat_with_fresh_letters():
    rule = from_dict({"rhyme": "ABAB"}).base
    assert [rule.rhyme_at(i) for i in range(8)] == [
        "A0",
        "B0",
        "A0",
        "B0",
        "A1",
        "B1",
        "A1",
        "B1",
    ]
    assert from_dict({"rhyme": "-A-A"}).base.rhyme_at(0) is None


def test_mixed_case_rhyme_sets_endings():
    rule = from_dict({"rhyme": "AbAb"}).base
    assert [rule.ending_at(i) for i in range(4)] == [1, 0, 1, 0]
    assert from_dict({"rhyme": "ABAB"}).base.ending_at(0) is None


@pytest.mark.parametrize(
    "data",
    [
        {"sylables": 8},
        {"syllables": "eight"},
        {"meter": "hexameter"},
        {"rhyme": "AB1B"},
        {"min_rhyme": "great"},
        {"language": "fr"},
        {"section": {"verse": {"colour": "red"}}},
        {"tolerance": -1},
    ],
)
def test_bad_specs_are_refused(data):
    with pytest.raises(SpecError):
        from_dict(data)


def test_templates_parse(tmp_path):
    for lang in ("hy", "ru"):
        path = tmp_path / f"{lang}.toml"
        path.write_text(template(lang), encoding="utf-8")
        spec = load(path)
        assert spec.language == lang
        assert spec.rule_for("verse").meter == "iamb"


def test_lexicon_keys_are_lowercased():
    spec = from_dict({"lexicon": {"Замок": "замо́к"}})
    assert spec.lexicon == {"замок": "замо́к"}
