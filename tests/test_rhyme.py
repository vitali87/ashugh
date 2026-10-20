import pytest

from ashugh import meter, rhyme
from ashugh.scan import analyze_lines
from ashugh.spec import Spec


def tails(a, b, lang):
    return [
        rhyme.tails(ln, meter.fit(ln.words, "free"))
        for ln in analyze_lines(f"{a}\n{b}", Spec(), lang)
    ]


def level(a, b, lang):
    return rhyme.level(rhyme.match(*tails(a, b, lang))[0])


@pytest.mark.parametrize(
    "a,b,expected",
    [
        ("правил", "заставил", "perfect"),
        ("занемог", "мог", "perfect"),
        ("ты", "красоты", "perfect"),
        ("любовь", "кровь", "perfect"),
        ("снег", "век", "perfect"),
        ("сердце", "дверце", "perfect"),
        ("тебя", "любя", "perfect"),
        ("любить", "жить", "perfect"),
        ("окон", "строгий", "assonance"),
        ("замок", "бьётся", "none"),
    ],
)
def test_russian_rhymes(a, b, expected):
    assert level(a, b, "ru") == expected


def test_russian_inexact_rhyme_is_not_perfect():
    assert level("ветер", "вечер", "ru") in ("near", "slant")


@pytest.mark.parametrize(
    "a,b,expected",
    [
        ("սեր", "տեր", "perfect"),
        ("քեզ", "մեզ", "perfect"),
        ("քաղաքին", "տանիքին", "perfect"),
        ("սեր", "ամպեր", "perfect"),
        ("սիրտ", "կյանք", "none"),
    ],
)
def test_armenian_rhymes(a, b, expected):
    assert level(a, b, "hy") == expected


def test_enclitic_joins_the_rhyme():
    a, b = tails("սիրում եմ", "տանում եմ", "hy")
    assert a[0].word == "սիրում եմ"
    assert rhyme.level(rhyme.match(a, b)[0]) == "perfect"


def test_scheme_detection():
    text = (
        "Мой дядя самых честных правил,\nКогда не в шутку занемог,\n"
        "Он уважать себя заставил\nИ лучше выдумать не мог."
    )
    ls = analyze_lines(text, Spec(), "ru")
    ts = [rhyme.tails(ln, meter.fit(ln.words, "iamb")) for ln in ls]
    assert rhyme.scheme(ts) == "ABAB"


@pytest.mark.parametrize(
    "a,b",
    [
        ("вселенной", "пленный"),
        ("благовонный", "утомлённой"),
        ("ограды", "отрада"),
        ("успех", "снег"),
    ],
)
def test_reduced_vowels_after_the_stress_still_rhyme(a, b):
    assert level(a, b, "ru") in ("perfect", "near")


@pytest.mark.parametrize("a,b", [("окон", "строгий"), ("замок", "бьётся"), ("ночь", "день")])
def test_non_rhymes_stay_out(a, b):
    assert level(a, b, "ru") not in ("perfect", "near")


def test_a_written_yo_is_not_read_as_e():
    from ashugh.scan import scan
    from ashugh.spec import from_dict

    text = "В томленьях грусти безнадёжной,\nЗвучал мне долго голос нежный\n"
    rep = scan(text, from_dict({"rhyme": "AA"}), lang="ru")
    assert "rhyme" in [i.code for i in rep.issues]


def test_promoted_tail_skips_an_elided_last_syllable():
    from ashugh import meter, rhyme
    from ashugh.lang import analyze
    from ashugh.lyrics import tokenize
    from ashugh.model import Line

    words = analyze("en", tokenize("and all the dioceses"), {})
    (k,) = [i for i, w in enumerate(words) if w.norm == "dioceses"]
    assert words[k].drop == words[k].size - 1
    fit = meter.fit_classical(words, "iamb", frozenset({k}), promote=True)
    assert fit.promoted and fit.count == 6
    line = Line(1, "and all the dioceses", "", "default", 0, 0, "en", words)
    tails = rhyme.tails(line, fit)
    assert all(t.vowel != "ə" for t in tails), [t.vowel for t in tails]
