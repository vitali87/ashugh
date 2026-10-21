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
