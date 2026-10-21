"""Round 12 of dogfooding: the workflow tools."""

import pytest

from ashugh.scan import scan
from ashugh.spec import from_dict


@pytest.mark.parametrize(
    "line",
    [
        "Carry me back where my love waits for me",
        "Carry me back where my love calls to me",
    ],
)
def test_a_free_pronoun_takes_the_last_beat_of_a_dactyl(line):
    rep = scan(line + "\n", from_dict({"language": "en", "meter": "dactyl4"}))
    assert rep.ok, [i.message for i in rep.issues]


def test_spec_from_reads_the_pronoun_ending_as_masculine():
    from ashugh.translate import derive_spec

    rep = scan("Carry me back where my love waits for me\n", from_dict({"language": "en"}))
    assert derive_spec(rep, set()).get("endings", "m").startswith("m")


def _pick(text, candidates, spec):
    from ashugh.fit import fit_song
    from ashugh.proposers import StaticProposer

    return fit_song(text, from_dict(spec), StaticProposer(candidates), rounds=1)


def test_an_unresolved_line_says_why_each_candidate_failed():
    text = "Я шёл домой\nИ пел о том, что вижу я\n"
    res = _pick(text, {2: ["Скажи мне слово, скажи сгоряча!"]}, {"language": "ru", "syllables": 4})
    u = next(u for u in res.unresolved if u.line == 2)
    assert u.rejected and "syllables" in u.rejected[0]["why"]
    assert u.rejected[0]["text"].startswith("Скажи")


def test_a_partner_waits_on_a_line_with_no_candidates():
    text = "I walked along the road\nAnd sang into the night\n"
    res = _pick(text, {}, {"language": "en", "rhyme": "AA"})
    reasons = " ".join(r for u in res.unresolved for r in u.reasons)
    assert "no candidates given" in reasons


def test_copies_of_a_chorus_get_the_same_repair():
    chorus = "The light is gone from all of the halls\n"
    text = f"[Chorus]\n{chorus}\n[Verse]\nI walk alone through every night\n\n[Chorus]\n{chorus}"
    candidates = {
        2: [("We keep a candle in the halls", 0.8), ("We keep a lantern by the walls", 0.8)],
        8: [("We keep a lantern by the walls", 0.8), ("We keep a candle in the halls", 0.8)],
    }
    spec = {"language": "en", "syllables": 8}
    from ashugh.fit import fit_song
    from ashugh.proposers import StaticProposer

    cands = {k: [{"text": t, "faithfulness": f} for t, f in v] for k, v in candidates.items()}
    res = fit_song(text, from_dict(spec), StaticProposer(cands), rounds=1)
    new = {c.line: c.new for c in res.changes}
    assert new[2] == new[8]


def test_requests_ask_once_for_a_repeated_line():
    from ashugh.fit import requests_for

    chorus = "The light is gone from all of the halls\n"
    text = f"[Chorus]\n{chorus}\n[Verse]\nI walk alone through every night\n\n[Chorus]\n{chorus}"
    reqs = requests_for(text, from_dict({"language": "en", "syllables": 8}))
    lines = [r.line for r in reqs]
    assert 8 not in lines and next(r for r in reqs if r.line == 2).copies == [8]


def test_one_set_of_candidates_repairs_every_copy():
    from ashugh.fit import fit_song
    from ashugh.proposers import StaticProposer

    chorus = "The light is gone from all of the halls\n"
    text = f"[Chorus]\n{chorus}\n[Verse]\nI walk alone through every night\n\n[Chorus]\n{chorus}"
    res = fit_song(
        text,
        from_dict({"language": "en", "syllables": 8}),
        StaticProposer({2: ["We keep a candle in the halls"], 5: ["I walk alone through night"]}),
        rounds=1,
    )
    new = {c.line: c.new for c in res.changes}
    assert new.get(8) == new.get(2) == "We keep a candle in the halls"


class _Flaky:
    """Answers the first round, then fails."""

    name = "flaky"

    def __init__(self, answers):
        self.answers, self.calls = answers, 0

    def propose(self, requests):
        from ashugh.proposers import ProposerError

        self.calls += 1
        if self.calls > 1:
            raise ProposerError("proposer command exited 1")
        return {r.id: list(self.answers.get(r.line, [])) for r in requests}


def test_a_later_proposer_failure_keeps_the_earlier_rounds():
    from ashugh.fit import fit_song

    text = "I walked along the road all day\nAnd sang into the night so long\n"
    flaky = _Flaky({1: ["I walked the road all day"]})
    res = fit_song(text, from_dict({"language": "en", "syllables": 6}), flaky, rounds=3)
    assert [c.new for c in res.changes] == ["I walked the road all day"]
    assert any("round 2 failed" in w for w in res.warnings)


def test_a_first_round_failure_still_raises():
    from ashugh.fit import fit_song
    from ashugh.proposers import ProposerError

    class Broken:
        name = "broken"

        def propose(self, requests):
            raise ProposerError("no")

    with pytest.raises(ProposerError):
        fit_song(
            "I walked along the road all day\n",
            from_dict({"language": "en", "syllables": 6}),
            Broken(),
        )


def test_a_spec_that_cannot_be_met_is_warned_about():
    spec = from_dict(
        {"language": "en", "syllables": 8, "meter": "iamb4", "rhyme": "AbAb", "endings": "fmfm"}
    )
    rep = scan("I walked along the road all day\nAnd sang into the night\n", spec)
    warnings = [i.message for i in rep.issues if i.code == "spec"]
    assert any("iamb4 with a feminine ending, which has 9" in w for w in warnings)


def test_a_consistent_spec_is_not_warned_about():
    spec = from_dict({"language": "en", "syllables": [9, 8], "meter": "iamb4", "endings": "fm"})
    rep = scan("I walked along the road all day\nAnd sang into the night\n", spec)
    assert not [i for i in rep.issues if i.code == "spec"]


def test_a_stanza_past_the_spec_tables_is_warned_about():
    spec = from_dict({"language": "ru", "stanza": {"1": {"syllables": 4}}})
    rep = scan("Я шёл домой\n\nИ пел о том, что вижу я\n", spec)
    assert any("stanza 2 has no rules" in i.message for i in rep.issues if i.code == "spec")


@pytest.mark.parametrize("path", ["README.md", "skill/SKILL.md"])
def test_the_documented_spec_can_be_met(path):
    import re
    from pathlib import Path

    from ashugh.spec import loads

    doc = Path(__file__).resolve().parent.parent / path
    block = re.search(
        r"### The spec\n\n```toml\n(.*?)```|## The spec\n\n```toml\n(.*?)```", doc.read_text(), re.S
    )
    assert block is not None
    toml = next(g for g in block.groups() if g)
    spec = loads(toml)
    song = "Я шёл домой\n\n[Припев]\nЯ шёл домой\nЯ шёл домой\nЯ шёл домой\nЯ шёл домой\n"
    rep = scan(song, spec)
    assert not [i for i in rep.issues if i.code == "spec" and "no line can pass" in i.detail]


def test_requests_aim_at_the_partners_that_stay():
    from ashugh.fit import requests_for

    text = (
        "I walk alone into the night\n"
        "And see the stars give off their light\n"
        "I think of you the whole long day\n"
        "And wish that I were back at home\n"
    )
    reqs = {r.line: r for r in requests_for(text, from_dict({"language": "en", "rhyme": "AAAA"}))}
    assert set(reqs[3].rhyme_with) == {"night", "light"}
    assert set(reqs[4].rhyme_with) == {"night", "light"}


def _mcp(name, args):
    from ashugh import mcp

    return mcp.TOOLS[name][2](args)


def test_mcp_syllables_gives_the_range_syl_gives():
    out = _mcp("syllables", {"text": "Ու մութն է իջել մեր ճամփին", "lang": "hy"})["lines"][0]
    assert (out["fewest"], out["most"]) == (8, 9)


def test_mcp_pick_keeps_warnings_and_reports_ignored_apart():
    out = _mcp(
        "pick", {"lyrics": "Я шёл домой\n", "candidates": {"5": ["x"]}, "spec": "syllables = 4"}
    )
    assert "ignored" in out and isinstance(out["warnings"], list)


def test_mcp_requests_and_translate():
    out = _mcp("requests", {"lyrics": "I walked along the road all day\n", "spec": "syllables = 6"})
    assert out["requests"][0]["syllables"] == 6
    asked = _mcp("translate", {"lyrics": "Я шёл домой\n", "to": "en"})
    assert asked["requests"][0]["source"] == "Я шёл домой"
    done = _mcp(
        "translate",
        {"lyrics": "Я шёл домой\n", "to": "en", "candidates": {"1": ["I walked back home"]}},
    )
    assert "I walked back home" in done["text"]


@pytest.mark.parametrize("ident", ["L5", "5", 5, "l5"])
def test_a_proposer_answer_names_its_line_any_usual_way(ident):
    from ashugh.proposers import Request, parse_lines

    req = Request(id="L5", line=5, lang="en", original="x")
    out = parse_lines({"lines": [{"id": ident, "candidates": ["a line"]}]}, [req])
    assert out == {"L5": ["a line"]}


def test_a_latin_armenian_candidate_is_accepted_for_an_armenian_line():
    from ashugh.fit import fit_song
    from ashugh.proposers import StaticProposer

    text = "Արի ու էլի մի գնա ինձնից հեռու\n"
    res = fit_song(
        text,
        from_dict({"language": "hy", "syllables": 6}),
        StaticProposer({1: ["Ari u el mi gna"]}),
        rounds=1,
    )
    assert not any("not in Armenian" in r["why"] for u in res.unresolved for r in u.rejected)
