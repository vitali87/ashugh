import pytest

from ashugh import evaluate, fit
from ashugh.scan import scan
from ashugh.spec import SpecError, from_dict

SONNET = """I walked along the river every day
And waited for the coming of the night
To see the moon pour out its silver light
Upon the water and the stony way

And still I walk there, for I cannot stay
Away from all that once was clear and bright
The heron and the willow in my sight
The patient stones gone soft and green and gray

I ask the water what it knows of me
It answers only with the wind and rain
It carries everything away to sea

And leaves the stones and me to start again
I think it wants to see the heron free
And so I come to stand there in the rain
"""

PETRARCHAN = {"rhyme": "ABBA ABBA CDC DCD", "language": "en"}


def errors(rep, code="rhyme"):
    return [(i.line, i.code) for i in rep.issues if i.severity == "error" and i.code == code]


def test_scheme_spans_stanzas():
    rep = scan(SONNET, from_dict(PETRARCHAN))
    assert rep.ok, [(i.line, i.message, i.detail) for i in rep.issues if i.severity == "error"]
    assert [u.rule.rhyme for u in rep.units] == ["ABBA", "ABBA", "CDC", "DCD"]


def test_a_rhyme_broken_across_stanzas_is_found():
    broken = SONNET.replace("soft and green and gray", "soft and green and cold")
    rep = scan(broken, from_dict(PETRARCHAN))
    (issue,) = [i for i in rep.issues if i.code == "rhyme"]
    assert issue.line == 9 and issue.data["with_line"] == 1  # stanza 2's A answers stanza 1's


def test_without_spaces_the_scheme_is_per_stanza():
    rep = scan(SONNET, from_dict({"rhyme": "ABBAABBACDCDCD", "language": "en"}))
    assert any(i.code == "scheme" for i in rep.issues)


def test_one_stanza_reads_the_spaced_scheme_as_a_whole():
    one = SONNET.replace("\n\n", "\n")
    assert scan(one, from_dict(PETRARCHAN)).ok


def test_letters_repeat_with_fresh_groups_after_the_scheme_ends():
    text = "day\nnight\n\nway\nlight\n\nsea\nstone\n\nfree\nalone\n"
    rep = scan(text, from_dict({"rhyme": "AB AB", "language": "en"}))
    assert rep.ok  # stanzas 3-4 start a new cycle: sea/free, stone/alone
    bad = "day\nnight\n\nway\nlight\n\nsea\nstone\n\nday\nalone\n"
    assert errors(scan(bad, from_dict({"rhyme": "AB AB", "language": "en"})))


@pytest.mark.parametrize("bad", ["AB1 AB", "AB  !", "ABAB -X?"])
def test_bad_spaced_schemes_are_refused(bad):
    with pytest.raises(SpecError):
        from_dict({"rhyme": bad})


def test_describe_keeps_the_stanza_breaks():
    spec = from_dict(PETRARCHAN)
    assert "ABBA ABBA CDC DCD" in evaluate.describe(spec)


class Scripted:
    name = "scripted"

    def __init__(self, answers):
        self.answers, self.calls = answers, []

    def propose(self, requests):
        self.calls.append(list(requests))
        return {r.id: self.answers.get(r.line, []) for r in requests}


def test_fit_repairs_a_cross_stanza_rhyme_with_its_partner_in_view():
    broken = SONNET.replace("soft and green and gray", "soft and green and cold")
    proposer = Scripted({9: ["The patient stones gone soft and green and gray"]})
    result = fit.fit_song(broken, from_dict(PETRARCHAN), proposer, rounds=1)
    assert result.ok
    (requests,) = proposer.calls
    (req,) = [r for r in requests if r.line == 9]
    assert sorted(req.rhyme_with) == ["day", "stay", "way"]  # stanza 1's A lines too


def test_a_section_tag_starts_the_scheme_over():
    text = "[Verse 1]\nday\nnight\n\n[Verse 2]\nsea\nstone\n\nfree\nalone\n"
    rep = scan(text, from_dict({"rhyme": "AB AB", "language": "en"}))
    assert [u.rule.rhyme for u in rep.units] == ["ABAB", "AB", "AB"]
    assert errors(rep) == []  # Verse 1 is read alone, not as the first half of Verse 2


def test_stress_is_chosen_with_partners_in_other_stanzas():
    text = (
        "Плывут над нами облака\nУходит в поле тёмный день\n\n"
        "Я слышу зов издалека\nЛожится на дорогу тень\n"
    )
    rep = scan(text, from_dict({"rhyme": "AB AB", "language": "ru", "meter": "iamb"}))
    assert errors(rep) == []  # облака́ / издалека́, not о́блака
    first = rep.units[0].lines[0]
    assert first.fit.stresses[3] == 2


def test_too_few_stanzas_for_the_scheme_is_a_warning():
    short = SONNET.split("\n\n")
    rep = scan("\n\n".join(short[:3]), from_dict(PETRARCHAN))
    (warn,) = [i for i in rep.issues if i.code == "scheme"]
    assert warn.severity == "warning" and warn.line == 13
    assert "3 stanzas" in warn.message and "4" in warn.message
    assert errors(rep) == []  # the D line has no partner yet: nothing to call broken


def test_whole_cycles_raise_no_scheme_warning():
    rep = scan(SONNET, from_dict(PETRARCHAN))
    assert [i for i in rep.issues if i.code == "scheme"] == []


def test_a_stanza_table_that_leaves_the_rhyme_alone_keeps_the_shared_scheme():
    spec = from_dict({**PETRARCHAN, "stanza": {"3": {"tolerance": 1}}})
    rep = scan(SONNET, spec)
    assert [u.rule.rhyme for u in rep.units] == ["ABBA", "ABBA", "CDC", "DCD"]
    assert rep.units[2].rule.tolerance == 1 and rep.units[3].rule.tolerance == 0
    broken = scan(SONNET.replace("soft and green and gray", "soft and green and cold"), spec)
    assert errors(broken) == [(9, "rhyme")]


def test_a_stanza_with_its_own_scheme_leaves_the_shared_run():
    spec = from_dict({**PETRARCHAN, "stanza": {"4": {"rhyme": "ABA"}}})
    rep = scan(SONNET, spec)
    assert [u.rule.rhyme for u in rep.units] == ["ABBA", "ABBA", "CDC", "ABA"]
    (warn,) = [i for i in rep.issues if i.code == "scheme"]
    assert "3 stanzas" in warn.message


def test_endings_follow_the_whole_schemes_case():
    text = (
        "I see the winter sky\nI walk along the river\n\n"
        "I walk along the way\nI wait for you all day\n"
    )
    rep = scan(text, from_dict({"rhyme": "aB CC", "language": "en"}))
    ending = sorted(i.line for i in rep.issues if i.code == "ending")
    assert ending == [4, 5]  # CC asks feminine endings; way / day are masculine
    whole = scan(text.replace("\n\n", "\n"), from_dict({"rhyme": "aBCC", "language": "en"}))
    assert sorted(i.line for i in whole.issues if i.code == "ending") == [3, 4]


def test_all_capital_parts_alone_ask_no_endings():
    rep = scan(SONNET, from_dict(PETRARCHAN))
    assert [i for i in rep.issues if i.code == "ending"] == []


def test_each_line_is_judged_by_its_own_stanzas_min_rhyme():
    text = (
        "I lost the track of time\nI held a hand in mine\n\n"
        "I sat upon a stone\nI could not find my home\n"
    )
    strict_second = {"rhyme": "AA BB", "language": "en", "stanza": {"2": {"min_rhyme": "perfect"}}}
    assert errors(scan(text, from_dict(strict_second))) == [(5, "rhyme")]
    loose_first = {
        "rhyme": "AA BB",
        "language": "en",
        "min_rhyme": "perfect",
        "stanza": {"1": {"min_rhyme": "near"}},
    }
    assert errors(scan(text, from_dict(loose_first))) == [(5, "rhyme")]


def test_fit_judges_a_shared_rhyme_like_scan_does():
    spec = from_dict(
        {
            "language": "en",
            "rhyme": "AB AB",
            "syllables": 3,
            "min_rhyme": "perfect",
            "stanza": {"2": {"min_rhyme": "near"}},
        }
    )
    text = "all the day\non a stone\n\non the way\nI am all alone\n"
    proposer = Scripted({5: ["far from home"]})
    result = fit.fit_song(text, spec, proposer, rounds=1)
    assert result.ok  # line 5 is judged near, in fit as in the rescan
    assert "far from home" in result.text


def test_only_partners_in_the_same_group_choose_a_stress():
    text = (
        "Над рекою старый замок\nНа столе так много банок\n\n"
        "Я под ливнем весь намок\nИ ступил через порог\n"
    )
    rep = scan(text, from_dict({"rhyme": "AA BB", "language": "ru", "meter": "dolnik"}))
    assert errors(rep) == []  # за́мок / ба́нок; намок is a B line
    assert rep.units[0].lines[0].fit.stresses[2] == 0


def test_rhyme_flag_overrides_stanza_tables_too(tmp_path, capsys):
    from ashugh.cli import main

    song = tmp_path / "song.txt"
    song.write_text("day\nnight\n\nway\nlight\n", encoding="utf-8")
    spec = tmp_path / "song.toml"
    spec.write_text('language = "en"\nrhyme = "AB"\n[stanza.2]\nrhyme = "AA"\n', encoding="utf-8")
    assert main(["scan", str(song), "--spec", str(spec)]) == 1  # way / light, as AA
    capsys.readouterr()
    assert main(["scan", str(song), "--spec", str(spec), "--rhyme", "AB AB"]) == 0
