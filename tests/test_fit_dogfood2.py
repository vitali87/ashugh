"""fit and pick, from the second dogfooding round."""

from ashugh import fit
from ashugh.fit import replace_lines
from ashugh.proposers import StaticProposer, parse_candidates
from ashugh.spec import from_dict


class Scripted:
    name = "scripted"

    def __init__(self, rounds):
        self.rounds, self.calls = list(rounds), []

    def propose(self, requests):
        self.calls.append(list(requests))
        answers = self.rounds.pop(0) if self.rounds else {}
        return {r.id: answers.get(r.line, []) for r in requests}


def test_a_candidate_whose_rhyme_chooses_the_stress_of_a_fixed_line():
    spec = from_dict({"language": "ru", "meter": "iamb", "rhyme": "AA"})
    text = "Плывут по небу облака,\nИ ветер тихо шелестит.\n"
    result = fit.fit_song(text, spec, StaticProposer({2: ["И песня льётся свысока."]}), rounds=1)
    assert result.ok and "свысока" in result.text


def test_a_candidate_in_another_language_is_refused():
    spec = from_dict({"language": "ru", "syllables": 6})
    text = "Ночь холодна и долга\n"
    result = fit.fit_song(text, spec, StaticProposer({1: ["The night is long and cold"]}), rounds=1)
    assert not result.ok and "The night" not in result.text


def test_translate_refuses_candidates_in_the_source_language():
    from ashugh.translate import translate_song

    src = "The night is cold and long,\nI sing my lonely song.\n"
    same = StaticProposer({1: ["The night is cold and long"], 2: ["I sing a lonely song"]})
    result = translate_song(src, "ru", same)
    assert not result.ok


def test_the_proposer_answer_format_works_as_a_candidates_file():
    answer = {"lines": [{"id": "L3", "candidates": ["one", {"text": "two", "faithfulness": 0.9}]}]}
    assert parse_candidates(answer) == {3: ["one", {"text": "two", "faithfulness": 0.9}]}
    assert parse_candidates({"L3": ["x"], "4": ["y"]}) == {3: ["x"], 4: ["y"]}


def test_the_template_follows_a_feminine_rhyme():
    spec = from_dict({"language": "ru", "meter": "iamb4", "rhyme": "AA"})
    reqs = fit.requests_for("Ночная улица пустая,\nИ снег идёт тихо, тая,\n", spec)
    by_line = {r.line: r for r in reqs}
    assert by_line[2].template == "x/x/x/x/x"


def test_no_line_rhymes_with_the_same_word_as_another():
    spec = from_dict({"language": "en", "syllables": 4, "rhyme": "AAA"})
    text = "The night is cold,\nMy heart is old,\nThe stars are shining bright and bold.\n"
    alone = fit.fit_song(text, spec, StaticProposer({3: ["Your heart is old."]}), rounds=1)
    assert "Your heart is old." not in alone.text  # old / old with line 2
    options = ["Your heart is old.", "The night is cold.", "The wind is bold."]
    result = fit.fit_song(text, spec, StaticProposer({3: options}), rounds=1)
    assert result.ok and result.text.splitlines()[2] == "The wind is bold."


def test_a_carried_backing_vocal_takes_the_new_lines_full_stop():
    out = replace_lines("I sing my lonely, lonely song (oh baby).\n", {1: "I sing a lonely tune."})
    assert out == "I sing a lonely tune (oh baby).\n"


def test_translation_does_not_carry_a_source_backing_vocal():
    out = replace_lines("Night is long, (so long)\n", {1: "Ночь длинна"}, lang="ru", asides=False)
    assert out == "Ночь длинна,\n"


def test_the_next_round_hears_about_near_misses():
    spec = from_dict({"language": "en", "syllables": 4, "rhyme": "AA"})
    text = "The night is cold and long,\nMy heart is old,\n"
    proposer = Scripted([{1: ["I sing a song"]}, {}])
    fit.fit_song(text, spec, proposer, rounds=2)
    (second,) = [r for r in proposer.calls[1] if r.line == 1]
    assert any("I sing a song" in rej for rej in second.rejected)


def test_a_group_that_is_all_rewritten_aims_at_its_first_line():
    spec = from_dict({"language": "en", "syllables": 3, "rhyme": "AA"})
    text = "Oh, that is so nice\nAnd I walk down the street\n"
    reqs = {r.line: r for r in fit.requests_for(text, spec)}
    assert reqs[1].rhyme_with == ["nice"] and reqs[2].rhyme_with == ["nice"]
