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


def counts(text: str, lang: str | None = None) -> list[tuple[int, str, int]]:
    """Each line's count, stress grid and number of words."""
    rep = scan(text, from_dict({"language": lang} if lang else {}))
    return [(lr.fit.count, lr.fit.grid, len(lr.line.words)) for lr in rep.lines]


def nfd(text: str) -> str:
    import unicodedata

    return unicodedata.normalize("NFD", text)


@pytest.mark.parametrize(
    "line, lang",
    [("Мой тёплый дом, ещё зимой", "ru"), ("A naïve café", "en"), ("Իմ տունը", "hy")],
)
def test_decomposed_letters_count_as_composed(line, lang):
    assert counts(nfd(line), lang) == counts(line, lang)


def test_suno_writes_decomposed_text_as_composed():
    plain = suno.format_song("Мой тёплый дом\n", tags=False).text
    assert suno.format_song(nfd("Мой тёплый дом\n"), tags=False).text == plain
    assert "̈" not in plain


@pytest.mark.parametrize("mark", ["´", "`", "‘", "′", "ʼ"])
def test_any_apostrophe_inside_a_word_is_an_apostrophe(mark):
    assert counts(f"I don{mark}t know", "en") == counts("I don't know", "en")


@pytest.mark.parametrize("dash", ["‐", "‑"])
def test_a_unicode_hyphen_inside_a_word_is_a_hyphen(dash):
    assert counts(f"по{dash}моему", "ru") == counts("по-моему", "ru")


@pytest.mark.parametrize("mark", ["­", "​", "‌", "‍", "⁠", "﻿"])
@pytest.mark.parametrize("word, lang", [("старых", "ru"), ("forever", "en"), ("սիրում", "hy")])
def test_an_invisible_character_inside_a_word_does_not_split_it(mark, word, lang):
    at = len(word) // 2
    assert counts(word[:at] + mark + word[at:], lang) == counts(word, lang)


def test_quotes_at_the_edges_of_a_word_stay_quotes():
    assert counts("‘Hello’ she said `softly`", "en") == counts("Hello she said softly", "en")


def test_cleaning_keeps_the_lines_where_they_are():
    rep = scan("I walk​\n­\nthe way\n", from_dict({"language": "en"}))
    assert [lr.line.number for lr in rep.lines] == [1, 3]


def test_syllables_tool_reads_a_spacing_acute_apostrophe():
    from ashugh.scan import analyze_lines
    from ashugh.spec import Spec

    (ln,) = analyze_lines("I don´t know", Spec(language="en"))
    assert [w.text for w in ln.words] == ["I", "don't", "know"]
