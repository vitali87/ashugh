"""Round 14 of dogfooding, Russian: what a songwriter found wrong."""

import pytest

from ashugh import meter, rhyme, suno
from ashugh.lang import ru
from ashugh.scan import analyze_lines, scan
from ashugh.spec import Spec, from_dict


def line_words(line: str):
    (ln,) = analyze_lines(line, Spec(language="ru"))
    return ln.words


def last_stresses(line: str) -> list[int | None]:
    return [r.stress for r in line_words(line)[-1].readings]


def rhymes(a: str, b: str) -> float:
    lines = analyze_lines(f"{a}\n{b}", Spec(language="ru"))
    return rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))[0]


@pytest.mark.parametrize(
    "phrase",
    [
        "в моей груди",
        "в твоей крови",
        "в ночной тиши",
        "в глухой ночи",
        "в лесной глуши",
        "на моей груди",
        "в ночной степи",
    ],
)
def test_the_second_locative_is_end_stressed_after_a_feminine_adjective(phrase):
    w = line_words(phrase)[-1]
    assert [r.stress for r in w.readings] == [w.size - 1]


def test_grudi_rhymes_with_uhodi_after_moyey():
    assert rhymes("Сердце бьётся в моей груди", "Не молчи и не уходи") >= rhyme.THRESHOLD["near"]


@pytest.mark.parametrize("phrase", ["в большой саду", "у моей груди"])
def test_other_phrases_are_left_alone(phrase):
    # a masculine noun after a feminine form, and no в or на before the adjective
    w = line_words(phrase)[-1]
    assert w.readings[0].stress == ru.analyze_word(w.text).readings[0].stress


@pytest.mark.parametrize(
    "word, first, other",
    [("мою", 1, 0), ("стоим", 1, 0), ("стоят", 1, 0), ("выходи", 2, 0), ("жила", 1, 0)],
)
def test_the_frequent_reading_of_a_homograph_comes_first(word, first, other):
    assert [r.stress for r in ru.analyze_word(word).readings] == [first, other]


@pytest.mark.parametrize(
    "line, out",
    [
        ("Ты держишь мою ладонь\n", "моЮ"),
        ("Деревья стоят у реки\n", "стоЯт"),
    ],
)
def test_suno_writes_the_frequent_reading(line, out):
    assert out in suno.format_song(line, tags=False).text


VODY = "Ушли под лёд холодные воды,\nУшли за ними наши годы.\n"


def test_a_detected_meter_does_not_veto_the_reading_a_spec_rhyme_needs():
    rep = scan(VODY, from_dict({"language": "ru", "rhyme": "AA"}))
    assert rep.ok, [i.message for i in rep.issues if i.severity == "error"]
    assert rep.lines[0].fit.stresses[4] == 0  # во́ды


def test_suno_writes_the_rhyme_reading_with_a_detected_meter():
    out = suno.format_song(VODY, spec=from_dict({"language": "ru", "rhyme": "AA"}), tags=False).text
    assert "водЫ" not in out


def test_a_meter_in_the_spec_still_limits_what_a_rhyme_may_buy():
    spec = from_dict({"language": "ru", "rhyme": "AA", "meter": "iamb"})
    rep = scan(VODY, spec)
    assert rep.lines[0].fit.stresses[4] == 1  # the iamb keeps воды́ and flags the rhyme
