"""Round 15 of dogfooding, Armenian: what a songwriter found wrong."""

import pytest

from ashugh import meter, rhyme
from ashugh.scan import analyze_lines
from ashugh.spec import Spec


def words(line: str, lang: str = "hy"):
    (ln,) = analyze_lines(line, Spec(language=lang))
    return ln.words


def es_is_pronoun(line: str, nth: int = 0) -> bool:
    es = [w for w in words(line) if w.norm == "ես"][nth]
    return not es.clitic


def hy_rhyme(a: str, b: str) -> float:
    lines = analyze_lines(f"{a}\n{b}", Spec(language="hy"))
    return rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))[0]


@pytest.mark.parametrize(
    "line",
    [
        "Ոչ ես, ոչ դու",
        "եթե ոչ ես",
        "Նույնիսկ ես",
        "Նաև ես",
        "Հենց ես",
        "Կամ ես, կամ դու",
        "Միայն ես",
    ],
)
def test_es_after_a_negation_or_focus_word_is_the_pronoun(line):
    assert es_is_pronoun(line)


@pytest.mark.parametrize("line", ["Ինչու ես լռում", "Դու իմ սերն ես"])
def test_es_after_its_word_stays_the_auxiliary(line):
    assert not es_is_pronoun(line)


def test_och_es_rhymes_on_es():
    assert hy_rhyme("Մնացինք դու ու ես", "Չմնաց ոչ ես") >= 0.9


def test_capital_yev_is_the_conjunction_not_letters():
    ws = words("Հայաստան ԵՎ Արցախ")
    assert sum(w.size for w in ws) == 6


@pytest.mark.parametrize("line", ["Իմ յար, աաա,", "Աաա, աաա"])
def test_a_held_vowel_is_a_vocable_not_the_auxiliary(line):
    held = [w for w in words(line) if w.norm.startswith("աաա")]
    assert held and all(not w.clitic and not w.enclitic for w in held)


def test_a_held_vowel_does_not_join_the_rhyme():
    from ashugh.scan import scan
    from ashugh.spec import from_dict

    report = scan("Իմ յար, աաա,\nԻմ յար։\n", from_dict({"language": "hy", "rhyme": "AA"}))
    assert not [i for i in report.issues if i.code == "rhyme" and i.severity == "error"]


@pytest.mark.parametrize(
    "text,lang,shown",
    [("beyond the yesterday", "en", "be-yónd"), ("yesterday", "en", "yés-ter-day")],
)
def test_the_acute_never_lands_on_a_glide_y(text, lang, shown):
    from ashugh.model import mark_stress

    acute = "\u0301"
    assert mark_stress("yond") == f"yo{acute}nd" and mark_stress("yes") == f"ye{acute}s"
    assert mark_stress("by") == f"by{acute}"  # a y that is the vowel keeps it


def test_the_armenian_middle_dot_ends_a_phrase():
    ws = words("Ես եմ․ Դու ես")
    assert ws[-1].clitic  # the auxiliary, as after . or :


def test_dzayn_with_article_may_sing_its_schwa():
    w = words("ձայնն")[0]
    assert w.size == 2 or w.optional is not None


@pytest.mark.parametrize("line", ["Ո՞ւր ես, իմ սեր", "Վա՜յ, իմ սեր"])
def test_suno_notes_carry_no_control_characters(line):
    from ashugh import suno

    out = suno.format_song(line + "\n", armenian="latin", tags=False)
    for note in out.notes:
        assert not any(ord(ch) < 32 for ch in note.new + note.word), note


def test_a_reduplication_in_a_backing_vocal_keeps_both_marks():
    from ashugh import suno

    out = suno.format_song("Իմ յար (Վա՜յ-վա՜յ)\n", armenian="latin", tags=False).text
    inner = out[out.index("(") + 1 : out.index(")")]
    assert inner.count("́") == 2 or inner.lower().count("!") == 2, inner


def test_schwa_mode_writes_the_sung_schwa_of_a_latin_name():
    from ashugh import suno

    out = suno.format_song("Իմ iPhone-ս\n", armenian="schwa", tags=False).text
    assert "iPhone-ըս" in out


@pytest.mark.parametrize("token,shown", [("ՍՊԱՍՈՒՄ", "ԸՍ-ՊԱ-ՍՈՒՄ"), ("ՄԿՐՏԻՉ", "ՄԸ-ԿԸՐ-ՏԻՉ")])
def test_a_word_in_capitals_keeps_them_with_its_schwas(token, shown):
    w = words(f"ՈՒ {token}")[-1]
    assert "-".join(s.text for s in w.syllables) == shown


def test_a_lexicon_word_in_capitals_keeps_them():
    from ashugh.lang import hy

    w = hy.analyze_word("ԿԱՅՍՐՈՒԹՅՈՒՆ", {"կայսրություն": "կայսըրություն"})
    assert "".join(s.text for s in w.syllables) == "ԿԱՅՍԸՐՈՒԹՅՈՒՆ"
