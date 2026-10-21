"""Round 17's debatable points that a songwriter would still call bugs."""

import pytest

from ashugh import lyrics
from ashugh.scan import scan
from ashugh.spec import from_dict

SONG = "[Verse]\nI walk along the road\nWith heavy load\n\n[{tag}]\nThe night is long\nAnd cold\n"


@pytest.mark.parametrize(
    "tag,head",
    [
        ("Double Chorus", "chorus"),
        ("Outro Chorus", "chorus"),
        ("Chorus Reprise", "chorus"),
        ("Rap Verse", "verse"),
        ("Middle 8", "bridge"),
        ("Middle Eight", "bridge"),
    ],
)
def test_a_compound_section_name_takes_its_head_sections_rules(tag, head):
    spec = from_dict({"language": "en", "section": {head: {"rhyme": "AA"}}})
    report = scan(SONG.format(tag=tag), spec)
    unit = report.units[-1]
    assert unit.rule.rhyme == "AA"
    assert not any("matches no section" in i.message for lr in report.lines for i in lr.issues)


def test_a_compound_name_of_its_own_keeps_its_own_table():
    spec = from_dict(
        {"language": "en", "section": {"chorus": {"rhyme": "AA"}, "double chorus": {"rhyme": "AB"}}}
    )
    assert scan(SONG.format(tag="Double Chorus"), spec).units[-1].rule.rhyme == "AB"


def test_a_spoken_bridge_stays_spoken():
    spec = from_dict({"language": "en", "syllables": 6, "section": {"bridge": {"rhyme": "AA"}}})
    text = "[Spoken Bridge]\nAnd then I told her everything I ever knew about the sea\n"
    assert scan(text, spec).ok


@pytest.mark.parametrize("name", ["Golden Hour", "Sunrise"])
def test_a_name_with_no_known_word_has_no_head(name):
    assert lyrics.section_head(lyrics.section_key(name)) is None


def _ru_words(line: str):
    from ashugh.scan import analyze_lines
    from ashugh.spec import Spec

    (ln,) = analyze_lines(line, Spec(language="ru"))
    return ln.words


@pytest.mark.parametrize("line", ["Всё о'кей, всё будет хорошо", "О'кей, мы едем домой"])
def test_okey_is_no_stress_mark(line):
    w = next(w for w in _ru_words(line) if "кей" in w.norm)
    assert w.readings[0].stress == 1 and not w.guessed


def test_an_apostrophe_after_an_inner_vowel_is_still_a_stress_mark():
    w = _ru_words("Замо'к стоит на горе")[0]
    assert w.readings[0].stress == 1 and w.readings[0].source == "mark"
