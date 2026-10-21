"""Round 12's adversarial findings: input that broke the tools."""

import pytest

from ashugh import lyrics, suno
from ashugh.scan import scan
from ashugh.spec import from_dict


def sections(text: str) -> list[tuple[str, str, str]]:
    return [(ln.text, ln.section, ln.key) for ln in lyrics.parse(text)]


@pytest.mark.parametrize(
    "tag",
    [
        "[Verse 1] [Male Vocal]",
        "[Verse 1](softly)",
        "[Verse 1]  (x2)  [Whispered]",
        "[Verse 1][Guitar]",
    ],
)
def test_a_tag_line_with_a_second_tag_or_an_aside_is_no_lyric(tag):
    assert sections(f"{tag}\nI walked along the river side\n") == [
        ("I walked along the river side", "Verse 1", "verse")
    ]


def test_a_second_tag_on_its_own_line_keeps_the_section():
    text = "[Chorus]\n[Female Vocal]\nOh river take me home\n"
    assert sections(text) == [("Oh river take me home", "Chorus", "chorus")]


def test_the_last_section_name_in_a_run_of_tags_opens_the_section():
    text = "[Intro]\n[Verse 1]\nI walked along the river side\n"
    assert sections(text)[0][2] == "verse"


def test_a_style_tag_after_lyric_lines_still_opens_a_stanza():
    text = "[Verse]\nI walked along\n[Spoken Word]\nAnd then I stopped\n"
    assert [ln.unit for ln in lyrics.parse(text)] == [0, 1]


def test_a_line_of_backing_vocals_alone_is_no_tag():
    assert not lyrics.is_tag("(oh) (yeah)")
    assert lyrics.is_tag("[Chorus] (softly)")
    assert not lyrics.is_tag("[Chorus] oh river")


def test_scan_counts_no_tag_text():
    rep = scan(
        "[Verse 1] [Male Vocal]\nI walked along the river side\n", from_dict({"syllables": 8})
    )
    assert [lr.line.number for lr in rep.lines] == [2] and rep.ok


def test_suno_keeps_a_tag_line_with_an_aside_and_adds_no_tag():
    out = suno.format_song("[Chorus] (softly)\nOh river take me home\n", tags=True).text
    assert out == "[Chorus] (softly)\nOh river take me home\n"


def test_suno_names_each_section_tag_on_a_tag_line():
    out = suno.format_song("[Припев] [Женский вокал]\nЯ жду\n", tags=True).text
    assert out.splitlines()[0] == "[Chorus] [Женский вокал]"


@pytest.mark.parametrize(
    "tag, key",
    [
        ("Verse Two", "verse"),
        ("Verse 2 - Rap", "verse"),
        ("Chorus - Female", "chorus"),
        ("Chorus – Female", "chorus"),
        ("Post Chorus", "post-chorus"),
        ("Chorus II", "chorus"),
        ("Куплет 1 - тихо", "verse"),
        ("Pre-Chorus", "pre-chorus"),
    ],
)
def test_section_tag_variants_name_their_section(tag, key):
    assert lyrics.section_key(tag) == key


@pytest.mark.parametrize(
    "tag, name",
    [
        ("Verse Two", "Verse 2"),
        ("Verse 2 - Rap", "Verse 2 - Rap"),
        ("Chorus II", "Chorus 2"),
        ("Куплет 1 - тихо", "Verse 1 - тихо"),
        ("Post Chorus", "Post-Chorus"),
        ("Pre-Chorus", "Pre-Chorus"),
    ],
)
def test_section_tag_variants_get_suno_names(tag, name):
    assert lyrics.suno_tag(tag) == name


def test_a_tag_naming_no_section_is_left_alone():
    assert lyrics.suno_tag("Male Vocal") is None
    assert lyrics.suno_tag("Chorus Line Dance") is None
