"""Round 17 of dogfooding, Armenian: what a songwriter found wrong."""

import pytest

from ashugh import lyrics, meter, rhyme
from ashugh.scan import analyze_lines, scan
from ashugh.spec import Spec, from_dict


def words(line: str, lang: str = "hy"):
    (ln,) = analyze_lines(line, Spec(language=lang))
    return ln.words


def langs(line: str, lang: str = "hy") -> list[str]:
    return [w.lang for w in words(line, lang)]


def hy_rhyme(a: str, b: str) -> float:
    lines = analyze_lines(f"{a}\n{b}", Spec(language="hy"))
    return rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))[0]


@pytest.mark.parametrize("line", ["Վերջ։", "Տուն։", "Վերջ:", "Տուն:", "End:"])
def test_a_one_word_sung_line_is_no_section_label(line):
    assert lyrics.plain_label(line) is None and not lyrics.is_tag(line)


@pytest.mark.parametrize(
    "line,tag",
    [
        ("Կրկներգ:", "[Կրկներգ]"),
        ("Տուն 2:", "[Տուն 2]"),
        ("Chorus:", "[Chorus]"),
        ("Bridge", "[Bridge]"),
    ],
)
def test_a_section_label_still_is_one(line, tag):
    assert lyrics.plain_label(line) == tag


def test_a_sung_verj_is_counted_and_kept_by_suno():
    from ashugh import suno

    text = "Արի ինձ մոտ, իմ յար,\nՎերջ։\n"
    report = scan(text, Spec(language="hy"))
    assert [lr.line.text for lr in report.lines] == ["Արի ինձ մոտ, իմ յար,", "Վերջ։"]
    out = suno.format_song(text, Spec(language="hy"), tags=False).text
    assert "Վերջ։" in out and "[End]" not in out


@pytest.mark.parametrize(
    "line,english",
    [
        ("Դու ինձ տանում ես higher", ["higher"]),
        ("Մենք պարում ենք laughing all night", ["laughing", "all", "night"]),
        ("Ես ու դու միասին ենք on the highway", ["on", "the", "highway"]),
        ("Իմ սիրտը քեզ մոտ է my neighbors know", ["my", "neighbors", "know"]),
    ],
)
def test_english_words_in_an_armenian_line_stay_english(line, english):
    ws = words(line)
    assert [w.text for w in ws if w.lang == "en"] == english


@pytest.mark.parametrize(
    "line,english",
    [
        ("Du sexy es, kez em sirum", ["sexy"]),
        ("Kez em spasum, next time mi gna", ["next", "time"]),
        ("Kyanqs party a, kez em sirum", ["party"]),
    ],
)
def test_a_latin_typed_line_borrows_pop_english(line, english):
    assert [w.text for w in words(line) if w.lang == "en"] == english


def test_an_english_line_with_gh_words_under_an_armenian_spec_is_english():
    assert set(langs("She laughs and sighs tonight")) == {"en"}
    assert sum(w.size for w in words("She laughs and sighs tonight")) == 6


@pytest.mark.parametrize(
    "line,count",
    [
        ("Ari, ari, mi gna", 7),
        ("Ari, ari, im bari jan", 8),
        ("Du im srtis mej es, my love", 8),
        ("Ari, ari, im anush yar", 8),
    ],
)
def test_latin_typed_armenian_that_looks_english_is_armenian(line, count):
    ws = words(line)
    assert sum(w.size for w in ws) == count
    assert all(w.lang == "hy" for w in ws if w.norm not in ("my", "love"))


def test_a_latin_typed_word_rhymes_with_its_armenian_spelling():
    assert hy_rhyme("ari", "բարի") >= rhyme.THRESHOLD["perfect"]


@pytest.mark.parametrize(
    "line", ["I love you baby", "Midnight city lights", "Dance with me tonight", "I need an inch"]
)
def test_english_lines_in_an_armenian_song_stay_english(line):
    assert set(langs(line)) == {"en"}


def test_burns_is_still_english():
    from ashugh.lang import latin_armenian

    for line in [
        "Thou need na start awa sae hasty,",
        "Wi' bickering brattle!",
        "Wee, sleekit, cow'rin, tim'rous beastie,",
    ]:
        assert not latin_armenian(lyrics.tokenize(line))


def test_a_latin_typed_candidate_is_accepted_for_a_latin_typed_song():
    from ashugh.fit import fit_song
    from ashugh.proposers import StaticProposer

    text = "Ari, ari, im anush yar,\nQez em spasum gisherov,\n"
    spec = from_dict({"language": "hy", "syllables": 8})
    result = fit_song(text, spec, StaticProposer({2: ["Ari, ari, im bari jan,"]}), rounds=1)
    rejected = [r["why"] for u in result.unresolved for r in u.rejected]
    assert not any("not in Armenian" in why for why in rejected)
