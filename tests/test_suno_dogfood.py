"""Suno spellings, line replacement and translation summaries from a dogfooding pass."""

from ashugh import suno
from ashugh.fit import replace_lines
from ashugh.lang import hy


def fmt(text, **kw):
    kw.setdefault("tags", False)
    return suno.format_song(text, **kw).text


def test_latin_mode_romanizes_backing_vocals_and_the_full_stop():
    out = fmt("Ես գնում եմ հեռու (հեռու)։\n", armenian="latin")
    assert "(herru)" in out and "։" not in out and out.rstrip().endswith(".")


def test_schwa_mode_writes_schwas_in_backing_vocals_too():
    assert "(ըս-պա-սում)" not in fmt("Ես սպասում եմ (սպասում)\n", armenian="schwa")
    assert "(ըսպասում)" in fmt("Ես սպասում եմ (սպասում)\n", armenian="schwa")


def test_a_written_stress_mark_survives_schwa_and_latin_modes():
    assert fmt("Ո՛րտեղ ես դու\n", armenian="schwa").startswith("Ո՛րտեղ")
    latin = fmt("Ո՛րտեղ ես դու\n", armenian="latin")
    assert latin.startswith("Vórtegh") or latin.startswith("Vórtegh")


def test_a_question_mark_on_a_word_becomes_a_question_in_latin():
    assert fmt("Ո՞ւր ես գնում\n", armenian="latin").split()[0].endswith("?")


def test_the_auxiliary_after_a_linking_n_has_no_y():
    assert "luysn es" in fmt("Դու իմ լույսն ես\n", armenian="latin")
    assert fmt("Ես եմ\n", armenian="latin").startswith("Yes")  # the pronoun keeps it


def test_capital_yev_is_the_conjunction_and_a_clitic():
    assert hy.analyze_word("Եվ").clitic and hy.analyze_word("և").clitic


def test_a_replaced_line_keeps_its_trailing_backing_vocal():
    text = "And every star went far away, (away)\nnext\n"
    out = replace_lines(text, {1: "And every star had gone to hide"})
    assert out.splitlines()[0] == "And every star had gone to hide, (away)"
    keep = replace_lines(text, {1: "And every star had gone (gone)"})
    assert keep.splitlines()[0] == "And every star had gone (gone)"  # it brought its own


def test_translate_counts_a_line_left_untranslated_as_failing():
    from ashugh.proposers import StaticProposer
    from ashugh.translate import translate_song

    result = translate_song("The night is long\nThe road is dark\n", "ru", StaticProposer({}))
    passing = sum(1 for lr in result.report.lines if lr.ok)
    assert passing == 0 and not result.ok
    assert any(i.code == "translate" for i in result.report.issues)
