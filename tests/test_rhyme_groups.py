"""A rhyme group holds when its lines rhyme with one another, not only with the first."""

from ashugh import fit
from ashugh.scan import scan
from ashugh.spec import from_dict


def errors(rep):
    return [(i.line, i.data.get("with_line")) for i in rep.issues if i.code == "rhyme"]


def test_a_line_that_rhymes_with_a_later_member_is_not_broken():
    text = "I write with a pen\nI follow to the end\nI call my friends\nAnd so it ends\n"
    rep = scan(text, from_dict({"language": "en", "rhyme": "AAAA"}))
    assert errors(rep) == []  # ends rhymes with friends, though only slant with pen


def test_the_first_line_can_be_the_one_that_breaks():
    text = "I hold a cup\nI follow to the end\nI call my friends\nAnd so it ends\n"
    rep = scan(text, from_dict({"language": "en", "rhyme": "AAAA"}))
    assert [line for line, _ in errors(rep)] == [1]


def test_two_pairs_under_one_letter_are_still_broken():
    text = "I walk the way\nI wait all day\nI dream at night\nI keep the light\n"
    rep = scan(text, from_dict({"language": "en", "rhyme": "AAAA"}))
    assert sorted(line for line, _ in errors(rep)) == [3, 4]  # the first line's pair stands


def test_the_larger_rhyming_set_stands_against_the_first_line():
    text = "I love the cold\nI walk the road\nI found the gold\nThe story told\n"
    rep = scan(text, from_dict({"language": "en", "rhyme": "AAAA", "min_rhyme": "perfect"}))
    assert errors(rep) == [(2, 1)]


class Scripted:
    name = "scripted"

    def __init__(self, answers):
        self.answers = answers

    def propose(self, requests):
        return {r.id: self.answers.get(r.line, []) for r in requests}


def test_fit_keeps_a_line_that_rhymes_through_another_member():
    text = "the time\nthe night\nis mine\nthe line\n"
    spec = from_dict({"language": "en", "rhyme": "AAAA", "min_rhyme": "near"})
    before = scan(text, spec)
    broken = {line for line, _ in errors(before)}
    assert broken == {2}  # night is the odd one; time, mine and line hold together
    result = fit.fit_song(text, spec, Scripted({2: ["the sign"]}), rounds=1)
    assert result.ok and "the sign" in result.text


def test_fit_does_not_hold_a_kept_line_to_the_first_one_alone():
    text = "I write with a pen\nI follow to the end\nI call my friends\nI hold a cup\n"
    spec = from_dict({"language": "en", "rhyme": "AAAA"})
    assert [line for line, _ in errors(scan(text, spec))] == [4]  # friends holds through end
    result = fit.fit_song(text, spec, Scripted({4: ["it never ends"]}), rounds=1)
    assert result.ok and "it never ends" in result.text
