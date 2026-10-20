import pytest

from ashugh import lang, lyrics, meter
from ashugh.scan import analyze_lines
from ashugh.spec import Spec


def lines(text):
    return analyze_lines(text, Spec(), "ru")


STANZAS = {
    "iamb": "Мой дядя самых честных правил,\nКогда не в шутку занемог,\n"
    "Он уважать себя заставил\nИ лучше выдумать не мог.",
    "trochee": "Буря мглою небо кроет,\nВихри снежные крутя;\n"
    "То, как зверь, она завоет,\nТо заплачет, как дитя,",
    "dactyl": "Тучи небесные, вечные странники!\nСтепью лазурною, цепью жемчужною",
    "anapest": "Вот парадный подъезд. По торжественным дням,",
    "amphibrach": "Однажды, в студёную зимнюю пору",
}


@pytest.mark.parametrize("name,text", STANZAS.items())
def test_detects_classical_meters(name, text):
    assert meter.detect(lines(text)) == name


def test_iamb_tetrameter_feet_and_endings():
    ls = lines(STANZAS["iamb"])
    fits = [meter.fit(ln.words, "iamb") for ln in ls]
    assert [f.feet for f in fits] == [4, 4, 4, 4]
    assert [f.ending for f in fits] == [1, 0, 1, 0]
    assert all(not f.off_beat and not f.ending_off for f in fits)


def test_meter_resolves_ambiguous_stress():
    (ln,) = lines("Мой дядя самых честных правил")
    f = meter.fit(ln.words, "iamb")
    assert f.stresses[4] == 0  # пра́вил, not прави́л


def test_off_beat_stress_is_reported():
    (ln,) = lines("Ты слышишь, как сердце бьётся")
    f = meter.fit(ln.words, "iamb")
    assert [ln.words[i].norm for i in f.off_beat] == ["сердце", "бьётся"]


def test_parse_meter():
    assert meter.parse_meter("iamb4") == ("iamb", 4)
    assert meter.parse_meter("Ямб") == ("iamb", None)
    with pytest.raises(ValueError):
        meter.parse_meter("hexameter")


def test_length_of_classical_lines():
    assert meter.length("iamb", 4, 0) == 8
    assert meter.length("iamb", 4, 1) == 9
    assert meter.length("anapest", 4, 0) == 12


def test_armenian_elision_chooses_the_count_that_fits():
    words = lang.analyze("hy", lyrics.tokenize("Նա ստացավ իր նամակը"), {})
    assert meter.fit(words, "free", count=8).count == 8
    assert meter.fit(words, "free", count=7).count == 7
