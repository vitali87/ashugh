"""Meter, from the ninth dogfooding round: ternary meters and the dolnik."""

import pytest

from ashugh.lang import en, ru
from ashugh.scan import scan
from ashugh.spec import from_dict

BYRON = (
    "Like the leaves of the forest when Summer is green,\n"
    "That host with their banners at sunset were seen:\n"
    "Like the leaves of the forest when Autumn hath blown,\n"
    "That host on the morrow lay withered and strown.\n"
)
BYRON_MID = (
    "And there lay the steed with his nostril all wide,\n"
    "But through it there rolled not the breath of his pride;\n"
)
FET = (
    "На заре ты её не буди,\nНа заре она сладко так спит;\n"
    "Утро дышит у ней на груди,\nЯрко пышет на ямках ланит.\n"
)


def errors(text: str, **spec) -> list[str]:
    rep = scan(text, from_dict(spec))
    return [f"L{i.line} {i.message}" for i in rep.issues if i.severity == "error"]


@pytest.mark.parametrize("text", [BYRON, BYRON_MID])
def test_an_english_anapest_takes_an_iambic_foot(text):
    assert errors(text, language="en", meter="anapest4") == []


def test_an_english_anapest_with_iambs_is_detected_as_one():
    rep = scan(BYRON, from_dict({"language": "en"}))
    assert {u.meter for u in rep.units} == {"anapest"}


@pytest.mark.parametrize(
    "line",
    [
        "The harbor lights are burning low",  # an iamb: every foot is short
        "The sun is low and the boats are home",  # two short feet in the line
    ],
)
def test_an_english_anapest_is_not_any_line_at_all(line):
    assert errors(line + "\n", language="en", meter="anapest4") != []


def test_russian_anapest_takes_a_stressed_word_before_its_first_beat():
    assert errors(FET, language="ru", meter="anapest3") == []
    rep = scan(FET, from_dict({"language": "ru"}))
    assert rep.units[0].meter == "anapest"


@pytest.mark.parametrize(
    "line, meter",
    [
        ("Комната тихо стоит у реки,", "anapest3"),  # the word runs past the first beat
        ("Утро дышит, и тихо в саду,", "iamb4"),  # an iamb has no two-syllable lead-in
    ],
)
def test_the_lead_in_licence_stays_inside_the_lead_in(line, meter):
    assert errors(line + "\n", language="ru", meter=meter) != []


def test_the_dolnik_takes_a_stressed_word_before_its_first_beat():
    text = "Смуглый отрок бродил по аллеям,\nУ озёрных грустил берегов,\n"
    assert errors(text, language="ru", meter="dolnik3") == []


def test_a_pronoun_after_a_preposition_may_end_a_dactyl_unstressed():
    text = (
        "Woman much missed, how you call to me, call to me,\n"
        "Saying that now you are not as you were\n"
        "When you had changed from the one who was all to me,\n"
    )
    assert errors(text, language="en", meter="dactyl4", rhyme="ABA") == []


def test_a_pronoun_after_a_preposition_still_rhymes_on_its_own():
    text = "So come and walk along with me,\nAnd I will set your spirit free.\n"
    assert errors(text, language="en", meter="iamb4", rhyme="AA") == []


@pytest.mark.parametrize(
    "word, count, stress",
    [("lances", 2, 0), ("pounces", 2, 0), ("twinges", 2, 0), ("sluices", 2, 0),
     ("solaces", 3, 0), ("besieges", 3, 1), ("interferences", 5, 2), ("rhapsodies", 3, 0)],
)  # fmt: skip
def test_an_unlisted_plural_is_its_singular_and_an_ending(word, count, stress):
    w = en.analyze_word(word)
    assert (w.size, w.readings[0].stress, w.guessed) == (count, stress, False)


@pytest.mark.parametrize("word, count", [("zorbances", 3), ("flumages", 3), ("snarbes", 1)])
def test_a_guessed_word_in_ces_or_ges_sings_its_es(word, count):
    assert en.analyze_word(word).size == count


@pytest.mark.parametrize("word, stresses", [("бледна", [1, 0]), ("тонки", [1, 0])])
def test_short_adjectives_with_both_stresses(word, stresses):
    assert ru.analyze_word(word).stress_options() == stresses


def test_without_its_edge_the_genitive_is_stressed_on_the_stem():
    rep = scan("О весна без конца, без краю\n", from_dict({"language": "ru", "meter": "anapest3"}))
    lr = rep.lines[0]
    assert lr.fit.stresses[len(lr.line.words) - 1] == 0 and not rep.ok
    rep = scan("Я стою на самом краю\n", from_dict({"language": "ru"}))
    assert 1 in rep.lines[0].line.words[-1].stress_options()


@pytest.mark.parametrize(
    "word, sung",
    [("darkened", "dar-kened"), ("withered", "with-ered"), ("battered", "bat-tered"),
     ("widened", "wi-dened"), ("glovebox", "glove-box")],
)  # fmt: skip
def test_an_ed_ending_is_no_second_word(word, sung):
    assert en.analyze_word(word).sung() == sung


def test_a_guessed_word_is_warned_about_once_per_line():
    rep = scan("Кто создан из камня, кто создан из глины\n", from_dict({"language": "ru"}))
    assert len([i for i in rep.issues if i.code == "stress"]) == 1


def test_a_final_secondary_may_take_the_last_beat_of_an_english_anapest():
    text = (
        "And the sheen of their spears was like stars on the sea,\n"
        "When the blue wave rolls nightly on deep Galilee.\n"
    )
    assert errors(text, language="en", meter="anapest4", rhyme="AA") == []


@pytest.mark.parametrize("word, stress", [("саней", 1), ("саням", 1), ("санями", 1), ("санях", 1)])
def test_the_sleigh_is_stressed_on_its_ending(word, stress):
    assert ru.analyze_word(word).stress_options() == [stress]  # сане́й, as аэросане́й


def test_a_troika_line_with_the_sleigh_is_a_clean_anapest():
    assert errors("Не вернуть ни саней, ни коней,\n", language="ru", meter="anapest3") == []


def test_a_broken_rhyme_names_the_best_reading_either_line_could_take():
    text = (
        "Кофе остыл на краю стола,\nТени ползут по белой стене,\n"
        "Ты в эту ночь от меня ушла,\nИ тишина звенит в голове.\n"
    )
    rep = scan(text, from_dict({"syllables": 9, "rhyme": "ABAB", "tolerance": 1, "language": "ru"}))
    (issue,) = [i for i in rep.issues if i.code == "rhyme"]
    assert "slant 0.66" in issue.detail  # стене́ / голове́, not the rare сте́не's none
