"""Round 16 of dogfooding, Russian: what a songwriter found wrong."""

import pytest

from ashugh import meter, rhyme, suno
from ashugh.scan import analyze_lines, scan
from ashugh.spec import Spec, from_dict


def line_words(line: str):
    (ln,) = analyze_lines(line, Spec(language="ru"))
    return ln.words


def first(word: str) -> str:
    """The word's first reading as a spelling with an acute on its stress."""
    w = line_words(word)[0]
    r = w.readings[0]
    return w.sung(r.stress, mark=True)


def rhymes(a: str, b: str) -> float:
    lines = analyze_lines(f"{a}\n{b}", Spec(language="ru"))
    return rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))[0]


def sung(text: str, **kw) -> str:
    return suno.format_song(text, tags=False, **kw).text


@pytest.mark.parametrize(
    "word,shown",
    [
        ("писать", "пи-са́ть"), ("душе", "ду-ше́"), ("пора", "по-ра́"), ("знаком", "зна-ко́м"),
        ("стою", "сто-ю́"), ("помочь", "по-мо́чь"), ("волна", "вол-на́"), ("венец", "ве-не́ц"),
        ("готов", "го-то́в"), ("спешит", "спе-ши́т"), ("пошли", "по-шли́"),
    ],
)  # fmt: skip
def test_the_usual_homograph_is_read_first(word, shown):
    assert first(word) == shown


@pytest.mark.parametrize(
    "word,shown",
    [
        ("руки", "ру́-ки"), ("начало", "на-ча́-ло"), ("замок", "за́-мок"), ("пушке", "пу́-шке"),
        ("бочки", "бо́ч-ки"), ("пятках", "пя́т-ках"),
    ],
)  # fmt: skip
def test_word_frequency_does_not_override_a_close_call(word, shown):
    assert first(word) == shown


@pytest.mark.parametrize("word", ["вода", "воде", "коса", "ужин", "лекарство", "транспорт"])
def test_a_variant_no_one_says_is_no_reading(word):
    assert len({r.stress for r in line_words(word)[0].readings}) == 1


@pytest.mark.parametrize("word", ["замок", "мука", "орган", "хлопок", "пора", "броня"])
def test_real_homographs_keep_both_readings(word):
    assert len({r.stress for r in line_words(word)[0].readings}) == 2


@pytest.mark.parametrize(
    "a,b", [("вода", "свобода"), ("воде", "погоде"), ("коса", "проса"), ("небо", "оба")]
)
def test_a_phantom_stress_makes_no_rhyme(a, b):
    assert rhymes(a, b) < 0.45


@pytest.mark.parametrize(
    "line,out",
    [
        ("Я буду писать тебе", "Я буду писАть тебе"),
        ("Мне в душе так светло", "Мне в душЕ так светло"),
        ("Мне пора уходить", "Мне порА уходить"),
        ("Золотая коса до пояса", "Золотая коса до пояса"),
    ],
)
def test_suno_marks_the_usual_homograph(line, out):
    assert sung(line).splitlines()[-1] == out


@pytest.mark.parametrize(
    "word,shown",
    [
        ("создана", "со-зда-на́"), ("создано", "со́-зда-но"), ("созданы", "со́-зда-ны"),
        ("отдана", "от-да-на́"), ("начата", "на-ча-та́"), ("понята", "по-ня-та́"),
        ("взята", "взя-та́"), ("спасена", "спа-се-на́"), ("унесена", "у-не-се-на́"),
        ("спасен", "спа-сён"), ("передано", "пе́-ре-да-но"), ("выдана", "вы́-да-на"),
        ("выбрана", "вы́-бра-на"), ("дана", "да-на́"), ("дано", "да-но́"), ("даны", "да-ны́"),
    ],
)  # fmt: skip
def test_short_participles_take_their_class_stress(word, shown):
    assert first(word) == shown


@pytest.mark.parametrize("word", ["сделана", "оставлена", "сцена", "цена", "стена"])
def test_other_words_in_ana_or_ena_keep_their_own_stress(word):
    w = line_words(word)[0]
    assert not w.guessed and w.readings[0].stress != w.size - 1 or word in ("цена", "стена")


def test_the_yo_word_is_read_first_where_it_is_the_common_one():
    assert first("моем") == "мо-ём" and first("полет") == "по-лёт"
    assert sung("Ты в моем сердце навсегда").splitlines()[-1].startswith("Ты в моём")


@pytest.mark.parametrize(
    "word,shown", [("черта", "чер-та́"), ("весны", "ве-сны́"), ("шелка", "шел-ка́")]
)
def test_a_yo_twin_that_is_no_plural_does_not_come_first(word, shown):
    assert first(word) == shown


@pytest.mark.parametrize(
    "word,shown", [("звезды", "звё-зды"), ("слезы", "слё-зы"), ("сестры", "сёс-тры")]
)
def test_a_yo_plural_still_comes_first(word, shown):
    assert first(word) == shown


def test_suno_does_not_turn_the_sky_into_the_palate():
    out = sung("Мы глядели в небо,\nМы молчали оба.\n")
    assert "нёбо" not in out and "нЁбо" not in out


@pytest.mark.parametrize(
    "line", ["Ты в моём сердце навсегда", "Ты в твоём доме не одна", "Ты в моем сердце навсегда"]
)
def test_a_possessive_in_the_locative_may_sit_on_a_weak_beat(line):
    report = scan(line + "\n", from_dict({"language": "ru", "meter": "iamb", "feet": 4}))
    assert report.lines[0].ok, [i.message for i in report.lines[0].issues]
