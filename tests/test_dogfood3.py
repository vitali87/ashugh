"""Linguistic fixes from the third dogfooding round."""

import pytest

from ashugh import suno
from ashugh.lang import ru
from ashugh.scan import scan
from ashugh.spec import from_dict


def fmt(text, **kw):
    kw.setdefault("tags", False)
    return suno.format_song(text, **kw).text


@pytest.mark.parametrize(
    "line,meter,word",
    [
        ("И звезды горели над нами", "amphibrach", "звёзды"),
        ("Озера и реки молчали", "amphibrach", "озёра"),
        ("Слезы на глазах", "dactyl", "слёзы"),
    ],
)
def test_suno_writes_the_yo_of_the_reading_the_meter_chose(line, meter, word):
    out = fmt(line + "\n", spec=from_dict({"language": "ru", "meter": meter}))
    assert word in out.lower()


def test_suno_keeps_e_where_the_meter_chose_the_e_reading():
    out = fmt("Слезы на глазах\n", spec=from_dict({"language": "ru", "meter": "amphibrach"}))
    assert "слёзы" not in out.lower()  # слезы́, of a tear


def test_ne_takes_the_stress_of_byl_and_friends():
    rep = scan("Не было снега, и не было лета\n", from_dict({"language": "ru", "meter": "dactyl"}))
    assert [i for i in rep.issues if i.severity == "error"] == []
    rep = scan("Ты не была со мной\n", from_dict({"language": "ru", "meter": "iamb"}))
    assert [i for i in rep.issues if i.severity == "error"] == []  # не была́: no shift


@pytest.mark.parametrize(
    "word,stresses",
    [
        ("ветра", {0, 1}),
        ("ветров", {1}),
        ("ветрами", {1}),
        ("начался", {2}),
        ("началось", {2}),
        ("Наташа", {1}),
        ("Татьяна", {1}),
        ("Ирина", {1}),
        ("Андрей", {1}),
        ("Сергей", {1}),
        ("Игорь", {0}),
        ("Владимир", {1}),
        ("Павел", {0}),
        ("Иисус", {2}),
        ("диджей", {1}),
        ("Екатерина", {3}),
        ("Александр", {2}),
    ],
)
def test_russian_words_common_in_lyrics(word, stresses):
    assert {r.stress for r in ru.analyze_word(word).readings if r.source != "lean"} == stresses


def test_the_wind_rhymes_with_the_morning():
    text = "Как пели нам ветра\nДо самого утра\n"
    rep = scan(text, from_dict({"language": "ru", "meter": "iamb", "rhyme": "AA"}))
    assert [i for i in rep.issues if i.severity == "error"] == []


def test_in_the_airport_is_a_second_locative():
    rep = scan("Мы встретились в аэропорту\n", from_dict({"language": "ru"}))
    (lr,) = rep.lines
    assert lr.fit.stresses[3] == 4  # аэропорту́


@pytest.mark.parametrize(
    "word,phones", [("сердце", "sʲertsə"), ("солнце", "sontsə"), ("жене", "ʒɨnʲe")]
)
def test_unstressed_e_after_hard_consonants(word, phones):
    assert "".join(ru.analyze_word(word).readings[0].phones) == phones


def test_heart_rhymes_with_to_warm_up():
    from ashugh.cli import main

    assert main(["rhyme", "сердце", "согреться"]) == 0


@pytest.mark.parametrize(
    "a,b", [("fire", "retire"), ("desire", "admire"), ("higher", "inspire"), ("hour", "power")]
)
def test_ire_and_our_rhyme_however_the_dictionary_spells_them(a, b):
    from ashugh.cli import main

    assert main(["rhyme", a, b]) == 0


@pytest.mark.parametrize(
    "word,size,first",
    [("lovestruck", 2, "love"), ("lovebirds", 2, "love"), ("facetime", 2, "face")],
)
def test_an_unknown_compound_reads_as_its_two_words(word, size, first):
    from ashugh.lang import en

    w = en.analyze_word(word)
    assert w.size == size and w.readings[0].stress == 0 and w.syllables[0].text.lower() == first


@pytest.mark.parametrize("word", ["memory", "mystery", "misery", "victory"])
def test_er_before_a_final_y_may_drop(word):
    from ashugh.lang import en

    w = en.analyze_word(word)
    assert w.size == 3 and w.drop == 1
    rep = scan(f"I hold the {word} close\n", from_dict({"language": "en", "syllables": 6}))
    assert rep.ok


@pytest.mark.parametrize(
    "word,pieces", [("quiet", "qui-et"), ("Louisiana", "Lou-i-si-a-na"), ("queen", "queen")]
)
def test_more_english_pieces(word, pieces):
    from ashugh.lang import en

    assert "-".join(s.text for s in en.analyze_word(word).syllables) == pieces


def test_split_follows_the_meters_short_form_without_a_count():
    out = fmt("But every time you call my name\n", split="all").strip()
    assert "e-ve-ry" not in out and len([p for w in out.split() for p in w.split("-")]) == 8
