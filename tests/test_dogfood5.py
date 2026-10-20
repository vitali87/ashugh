"""Round five of dogfooding: RIFMA's errors and three expert users."""

import unicodedata

import pytest

from ashugh.lang import ru


def stressed(word: str) -> list[int | None]:
    return ru.analyze_word(word).stress_options()


@pytest.mark.parametrize(
    "word,want",
    [
        ("кому", [1]),
        ("никого", [2]),
        ("никому", [2]),
        ("никем", [1]),
        ("некому", [0]),
        ("нечему", [0]),
        ("некем", [0]),
        ("нечем", [0]),
    ],
)
def test_forms_of_kto_and_chto(word, want):
    assert stressed(word) == want  # кому́, never ко́му (of ком, a lump)


@pytest.mark.parametrize(
    "word,want",
    [("стараясь", [1]), ("боясь", [1]), ("улыбаясь", [2]), ("держась", [1]), ("смеясь", [1])],
)
def test_a_gerund_in_sь_takes_its_verbs_stress(word, want):
    assert stressed(word) == want  # стара́ясь from стара́юсь, not ста́раясь from ста́рая


@pytest.mark.parametrize("word,want", [("умылась", [1]), ("взялась", [1]), ("старался", [1])])
def test_a_past_form_in_sя_still_reads_like_its_plain_form(word, want):
    assert stressed(word) == want


@pytest.mark.parametrize("word", ["пенье", "пенья", "пенью", "пеньем"])
def test_penye_is_the_song_form_of_penie(word):
    assert stressed(word) == [0]  # пе́нье, as пе́ние; not пенье́ of пеньё (stumps)


def en_rhyme(a: str, b: str) -> float:
    from ashugh import meter, rhyme
    from ashugh.scan import analyze_lines
    from ashugh.spec import Spec

    lines = analyze_lines(f"{a}\n{b}", Spec(language="en"), "en")
    return rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))[0]


def test_an_object_pronoun_after_a_verb_leans_on_it():
    from ashugh.scan import scan
    from ashugh.spec import from_dict

    rep = scan(
        "Money, honey, I don't need it\n", from_dict({"language": "en", "meter": "trochee4"})
    )
    assert [i.code for i in rep.issues if i.severity == "error"] == []
    assert rep.units[0].lines[0].fit.ending == 1  # NEED it


def test_lines_ending_on_the_same_pronoun_rhyme_on_the_word_before():
    from ashugh import rhyme

    assert en_rhyme("I don't need it", "I don't want it") < rhyme.THRESHOLD["slant"]
    assert en_rhyme("I don't need it", "I can feel it") >= rhyme.THRESHOLD["slant"]
    assert en_rhyme("so hold me", "you told me") >= rhyme.THRESHOLD["perfect"]


def test_a_leaning_pronoun_may_still_carry_the_rhyme():
    from ashugh import rhyme

    assert en_rhyme("you know I love you", "I'll always be true") >= rhyme.THRESHOLD["perfect"]


def test_after_a_preposition_the_pronoun_keeps_its_stress():
    from ashugh.scan import scan
    from ashugh.spec import from_dict

    rep = scan("I'm waiting here for you\n", from_dict({"language": "en", "meter": "iamb3"}))
    assert rep.units[0].lines[0].fit.ending == 0


def test_an_ending_asked_by_the_rhymes_case_says_so():
    from ashugh.scan import scan
    from ashugh.spec import from_dict

    rep = scan("I walk the way\nI hold the light\n", from_dict({"language": "en", "rhyme": "Ab"}))
    (issue,) = [i for i in rep.issues if i.code == "ending"]
    assert issue.line == 1 and "capital A" in issue.detail and "feminine" in issue.detail


@pytest.mark.parametrize(
    "word,want", [("спою", [1]), ("споем", [1]), ("споёт", [1]), ("споют", [1])]
)
def test_spet_is_stressed_on_its_ending(word, want):
    assert stressed(word) == want  # спою́ / свою́, not спо́ю


def test_atlas_may_be_satin_where_the_meter_asks():
    assert set(stressed("атласом")) == {0, 1}  # а́тласом (atlas) or атла́сом (satin)


@pytest.mark.parametrize(
    "word,spelling,want",
    [
        ("Сережа", "серёжа", 1),
        ("Федор", "фёдор", 0),
        ("Семен", "семён", 1),
        ("Алеша", "алёша", 1),
        ("Артем", "артём", 1),
        ("Петр", "пётр", 0),
    ],
)
def test_names_with_yo(word, spelling, want):
    (r,) = ru.analyze_word(word).readings
    assert r.spelling == spelling and r.stress == want


@pytest.mark.parametrize("word,want", [("улыбалася", [2]), ("смеялася", [1])])
def test_the_old_lasya_reads_as_las(word, want):
    w = ru.analyze_word(word)
    assert stressed(word) == want and not w.guessed  # улыба́лася as улыба́лась


@pytest.mark.parametrize("word,want", [("вода", 1), ("душа", 1), ("урок", 1)])
def test_a_line_that_leaves_the_stress_open_takes_the_headwords(word, want):
    assert ru.analyze_word(word).readings[0].stress == want  # вода́ before во́да of вод


FOREST = "Мы идём с тобою по лесу,\nЯ иду к тебе по голосу.\n"


def test_a_rhyme_may_choose_the_stress_on_the_preposition():
    from ashugh.scan import scan
    from ashugh.spec import from_dict

    rep = scan(FOREST, from_dict({"language": "ru", "rhyme": "AA"}))
    assert [i for i in rep.issues if i.code == "rhyme"] == []  # по́ лесу / по́ голосу


def test_free_verse_rhymes_the_shifted_stress_too():
    from ashugh import meter, rhyme
    from ashugh.scan import analyze_lines
    from ashugh.spec import Spec

    lines = analyze_lines(FOREST, Spec(language="ru"), "ru")
    s, _, _ = rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))
    assert s >= rhyme.THRESHOLD["near"]


def test_the_note_and_suno_show_the_stress_on_the_preposition():
    from ashugh import suno
    from ashugh.scan import scan
    from ashugh.spec import from_dict

    spec = from_dict({"language": "ru", "rhyme": "AA", "meter": "trochee4"})
    notes = [i.message for i in scan(FOREST, spec).issues if i.code == "stress"]
    assert "«по лесу» read as по́ ле-су" in notes
    out = suno.format_song(FOREST, spec=spec, tags=False).text
    assert "пО лесу" in out


def test_in_free_verse_the_rhyme_picks_the_reading_shown_and_sung():
    from ashugh import suno
    from ashugh.scan import scan
    from ashugh.spec import from_dict

    text = "Тусим до утра,\nГород — наша игра,\n"
    spec = from_dict({"language": "ru", "meter": "free", "rhyme": "AA"})
    first = scan(text, spec).units[0].lines[0]
    assert first.fit.stresses[2] == 1  # утра́, as it rhymes with игра́
    assert "утрА" in suno.format_song(text, spec=spec, tags=False).text


def test_russian_backing_vocals_get_their_yo_back():
    from ashugh import suno

    out = suno.format_song("Это сердце мое (мое, еще)", tags=False).text
    assert out == "Это сердце моё (моё, ещё)"
    assert suno.format_song("Я жду (все)", tags=False).text == "Я жду (все)"  # все or всё


def syl_output(capsys, *argv: str) -> str:
    from ashugh.cli import main

    main(["syl", *argv])
    return unicodedata.normalize("NFC", capsys.readouterr().out)


def test_syl_shows_a_dropped_syllable_as_the_count_has_it(capsys):
    out = syl_output(capsys, "--meter", "iamb", "And every sailor that I know")
    assert out.split()[0] == "8" and "é-ve-ry" not in out and "éve-ry" in out
    out = syl_output(capsys, "--lang", "hy", "Դու իմ սերն ես")
    assert out.split()[0] == "4" and "սե́-ր(ը)ն" in out


def test_scan_shows_an_english_drop_too():
    from ashugh.scan import scan
    from ashugh.spec import from_dict

    lr = scan(
        "And every sailor that I know\n", from_dict({"language": "en", "meter": "iamb4"})
    ).lines[0]
    assert "eve-ry" in lr.sung


def test_the_json_names_the_dropped_syllable():
    from ashugh.report import as_dict
    from ashugh.scan import scan
    from ashugh.spec import from_dict

    rep = scan("And every sailor that I know\n", from_dict({"language": "en", "meter": "iamb4"}))
    (line,) = as_dict(rep)["sections"][0]["lines"]
    every = line["words"][1]
    assert every["dropped"] == 1 and len(every["syllables"]) - 1 == 2


def test_the_acute_lands_on_a_syllable_with_ev(capsys):
    assert "ա-րև́" in syl_output(capsys, "--lang", "hy", "արև")
