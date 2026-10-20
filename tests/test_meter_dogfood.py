"""Stress choices a meter's feet decide, and English variants that merge vowels."""

from ashugh import fit
from ashugh.lang import en
from ashugh.proposers import StaticProposer
from ashugh.scan import analyze_lines, check_line, scan
from ashugh.spec import Spec, from_dict

TROCHEE = {"language": "ru", "meter": "trochee4", "rhyme": "AA"}


def test_the_feet_choose_an_ambiguous_stress_on_a_line_alone():
    spec = from_dict(TROCHEE)
    (ln,) = analyze_lines("Где проходят облака\n", spec)
    lr = check_line(ln, spec.base, "trochee", "spec")
    assert lr.ok and lr.fit.feet == 4  # облака́, not о́блака with three feet


def test_fit_accepts_a_candidate_that_scan_would_accept():
    spec = from_dict(TROCHEE)
    assert scan("Горы смотрят свысока,\nГде проходят облака.\n", spec).ok
    text = "Горы смотрят свысока,\nУплывают тучи вдаль.\n"
    result = fit.fit_song(text, spec, StaticProposer({2: ["Где проходят облака"]}), rounds=1)
    assert result.ok and "облака" in result.text


def test_without_feet_the_reading_is_the_meters_own_choice():
    (ln,) = analyze_lines("Где проходят облака\n", Spec(language="ru"))
    free = check_line(ln, from_dict({"meter": "trochee"}).base, "trochee", "spec")
    assert free.fit.feet in (3, 4)  # nothing asks for four


def test_a_variant_that_merges_two_vowels_may_drop_one():
    w = en.analyze_word("ourselves")
    assert w.size == 3 and w.drop is not None
    rep = scan(
        "The carriage held but just ourselves\n", from_dict({"language": "en", "meter": "iamb4"})
    )
    assert [i for i in rep.issues if i.severity == "error"] == []


def test_a_word_with_two_primary_stresses_may_take_either():
    stresses = {r.stress for r in en.analyze_word("well-known").readings}
    assert stresses == {0, 1}
    assert {r.stress for r in en.analyze_word("thirteen").readings} == {0, 1}
    rep = scan("A well-known voice\n", from_dict({"language": "en", "meter": "iamb2"}))
    assert [i for i in rep.issues if i.severity == "error"] == []


def test_one_primary_stress_does_not_move_back():
    assert {r.stress for r in en.analyze_word("today").readings} == {1}
    assert {r.stress for r in en.analyze_word("river").readings} == {0}
