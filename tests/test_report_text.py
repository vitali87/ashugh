"""The text report: what a writer sees in the terminal."""

from ashugh import report
from ashugh.scan import scan
from ashugh.spec import from_dict


def test_analysis_only_lists_every_line_with_its_grid():
    out = report.text(scan("Я жду тебя\nА ты не идёшь\n", lang="ru", path="s.txt"))
    head, _, *rest = out.splitlines()
    assert head == "s.txt · Russian · no spec (analysis only)"
    rows = [r for r in rest if r.startswith("  L")]
    assert len(rows) == 2 and "x/x/" in rows[0] and "Я жду те-бя́" in rows[0]
    assert out.endswith("2/2 lines pass · 0 errors")


def test_free_verse_and_warnings_are_named():
    spec = from_dict({"language": "en", "meter": "free", "rhyme": "AABB"})
    out = report.text(scan("one night\nthe light\n", spec))
    assert "free verse" in out
    assert "warning: stanza has 2 lines, rhyme AABB wants 4" in out
    assert out.endswith("2/2 lines pass · 0 errors · 1 warning")


def test_notes_show_only_with_all():
    spec = from_dict({"language": "hy", "syllables": 7})
    text = "Լեռն է բոլորին գրկում\n"
    assert "note:" not in report.text(scan(text, spec))
    assert "note: fits if «Լեռն» drops its ը" in report.text(scan(text, spec), show_all=True)
