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
