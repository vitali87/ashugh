"""ես: the pronoun I [jes], or the auxiliary (you are) [es] that leans on the word before."""

import unicodedata

import pytest

from ashugh import lyrics, meter, rhyme, suno
from ashugh.lang import analyze
from ashugh.scan import analyze_lines
from ashugh.spec import Spec


def score(a: str, b: str) -> float:
    lines = analyze_lines(f"{a}\n{b}", Spec(language="hy"), "hy")
    return rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))[0]


def es_word(line: str, k: int = -1):
    words = analyze("hy", lyrics.tokenize(line), {}, line)
    found = [w for w in words if w.norm == "ես"]
    return found[k]


@pytest.mark.parametrize(
    "line", ["Դու գալիս ես", "Դու գեղեցիկ ես", "Ինչու ես լռում", "Դու իմ սերն ես", "Որտեղ ես, սեր"]
)
def test_the_auxiliary_leans_and_has_no_y(line):
    w = es_word(line, 0)
    assert w.enclitic and w.readings[0].phones[0] != "j"


@pytest.mark.parametrize(
    "line,k",
    [("Ես գնում եմ", 0), ("Հիմա ես գիտեմ", 0), ("Ես եմ, ես եմ", 1), ("Ու ես կգամ", 0)],
)
def test_the_pronoun_opens_its_clause_or_has_its_own_verb(line, k):
    w = es_word(line, k)
    assert not w.enclitic and w.readings[0].phones[0] == "j"


def test_the_auxiliary_rhymes_like_its_neighbours():
    a = score("գալիս ես", "լալիս եք")
    b = score("գալիս եմ", "լալիս եք")
    assert a == pytest.approx(b)  # [lisɛs] / [lisɛkʰ], as [lisɛm] / [lisɛkʰ]; not [lisjɛs]


@pytest.mark.parametrize(
    "line,want",
    [
        ("Հիմա ես գիտեմ", "Hima yes gitem"),
        ("Ես եմ, ես եմ", "Yes em, yes em"),
        ("Դու գեղեցիկ ես", "Du geghetsik es"),
    ],
)
def test_latin_letters_follow_the_same_reading(line, want):
    assert suno.format_song(line, armenian="latin", tags=False).text == want


def latin(text: str) -> str:
    out = suno.format_song(text, armenian="latin", tags=False).text
    return unicodedata.normalize("NFC", out)


def test_held_note_pieces_in_armenian_letters_keep_the_writers_marks():
    out = suno.format_song("Ինչո՞ւ ես լռում, քնի՛ր, օրո՜ր", split="all", tags=False).text
    assert out == "Ին-չո՞ւ ես լռում, քնի՛ր, օ-րո՜ր"  # the hidden ը stays hidden


@pytest.mark.parametrize(
    "line,want",
    [
        ("Ո՞ւր ես, ո՞ւր", "Úr es, úr?"),
        ("Ինչո՞ւ ես լռում", "Inchú es lərrum?"),
        ("Օրո՜ր, բալիկ", "Orór, balik!"),
        ("Ո՞ւր ես։ Եկ", "Úr es? Yek"),
    ],
)
def test_a_question_or_exclamation_mark_goes_to_the_end_of_its_sentence(line, want):
    assert latin(line) == want


def test_a_line_that_is_only_a_backing_vocal_is_romanized_too():
    assert latin("Քաղաքում\n(Քաղաքին, քաղաքին)") == "Kaghakum\n(Kaghakin, kaghakin)"


def test_a_new_line_keeps_the_authors_order_of_full_stop_and_backing_vocal():
    from ashugh.fit import replace_lines

    text = "Բալիկ իմ, իմ արև։ (օրո՜ր, օրո՜ր)\n"
    assert replace_lines(text, {1: "Բալիկ իմ ոսկի, իմ գանձ։"}, "hy") == (
        "Բալիկ իմ ոսկի, իմ գանձ։ (օրո՜ր, օրո՜ր)\n"
    )
    text = "I sing a song (oh baby).\n"
    assert replace_lines(text, {1: "I hum a tune."}, "en") == "I hum a tune (oh baby).\n"


def test_the_pick_summary_shows_the_line_as_written(tmp_path, capsys):
    import json

    from ashugh.cli import main

    song = tmp_path / "song.txt"
    song.write_text("Բալիկ իմ, իմ արև։ (օրո՜ր)\n", encoding="utf-8")
    cands = tmp_path / "c.json"
    cands.write_text(json.dumps({"1": ["Բալիկ իմ, իմ գանձ։"]}), encoding="utf-8")
    main(["pick", str(song), "--candidates", str(cands), "--syllables", "5", "--lang", "hy"])
    assert "→ Բալիկ իմ, իմ գանձ։ (օրո՜ր)" in capsys.readouterr().err
