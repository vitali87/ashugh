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


INTRO_SONG = (
    "[Intro]\nOh oh oh\n\nI walk the road alone\nThe night is cold as stone\n\n"
    "Stay with me, stay with me\nTill the morning sets us free\n\n"
    "I walk the road again\nThe sky is full of rain\n\n"
    "Stay with me, stay with me\nTill the morning sets us free\n"
)


def test_an_intro_tag_alone_still_lets_suno_tell_verses_from_choruses():
    from ashugh import suno

    out = suno.format_song(INTRO_SONG).text
    assert out.startswith("[Intro]\nOh oh oh\n\n[Verse 1]\n")
    assert out.count("[Chorus]") == 2 and "[Verse 2]" in out


def test_a_tagged_verse_of_two_stanzas_gets_no_tag_inferred():
    from ashugh import suno

    text = "[Verse]\nI walk the road alone\n\nThe night is cold as stone\n"
    assert suno.format_song(text).text == text


def test_a_song_with_verse_and_chorus_tags_is_left_as_tagged():
    from ashugh import suno

    text = "[Verse]\nI walk the road alone\n\n[Chorus]\nStay with me\n\nThe night is cold\n"
    assert "[Verse 2]" not in suno.format_song(text).text


def test_an_english_lexicon_entry_may_give_two_readings():
    spec = from_dict(
        {"language": "en", "syllables": 6, "lexicon": {"heaven": "HH EH1 V AH0 N|HH EH1 V N"}}
    )
    report = scan("And heaven and nature sing\n", spec)
    assert report.ok
    w = report.lines[0].line.words[1]
    assert all(r.source == "user" or r.source == "lexicon" for r in w.readings)


def test_each_reading_of_a_lexicon_entry_is_checked():
    from ashugh.spec import SpecError

    with pytest.raises(SpecError, match="not ARPABET"):
        from_dict({"language": "en", "lexicon": {"zorblax": "Z AO1 R B|Q Q"}})


@pytest.mark.parametrize("a,b", [("heaven", "given"), ("river", "forever")])
def test_consonance_on_a_weak_syllable_reaches_assonance(a, b):
    from ashugh import rhyme

    text = f"I found my {a}\nand all that you {b}\n"
    assert scan(text, from_dict({"language": "en", "rhyme": "AA", "min_rhyme": "assonance"})).ok
    assert not scan(text, from_dict({"language": "en", "rhyme": "AA"})).ok
    assert rhyme.THRESHOLD["assonance"] <= 0.3 < rhyme.THRESHOLD["slant"]


@pytest.mark.parametrize("text", ["the cat\nthe kit\n", "the table\nthe people\n"])
def test_unlike_consonants_or_a_bare_coda_are_still_no_rhyme(text):
    spec = from_dict({"language": "en", "rhyme": "AA", "min_rhyme": "assonance"})
    assert not scan(text, spec).ok


@pytest.mark.parametrize(
    "line,word",
    [("Hold on (repeat)", "Hold on"), ("Держись (2 раза)", "Держись"), ("Stay (twice)", "Stay")],
)
def test_a_repeat_in_words_writes_the_line_out(line, word):
    from ashugh import suno

    out = suno.format_song(f"[Chorus]\n{line}\n", tags=False).text
    assert out.splitlines()[1:] == [word, word]


def test_a_sung_twice_is_a_word():
    from ashugh import suno

    assert suno.format_song("I love you twice\n", tags=False).text == "I love you twice\n"


@pytest.mark.parametrize("line", ["Мы поем о любви", "Мы не поем", "Мы снова поем"])
def test_we_sing_with_yo(line):
    w = next(w for w in _ru_words(line) if w.norm == "поем")
    assert {r.spelling for r in w.readings} == {"поём"}


def test_i_will_eat_keeps_both():
    w = next(w for w in _ru_words("Я поем и пойду") if w.norm == "поем")
    assert {r.spelling for r in w.readings} == {"поем", "поём"}


def test_we_sing_does_not_rhyme_with_sovsem():
    spec = from_dict({"language": "ru", "rhyme": "AA"})
    assert not scan("Мы поем с тобой\nНе забыв совсем\n", spec).ok
