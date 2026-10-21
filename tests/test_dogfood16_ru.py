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


@pytest.mark.parametrize(
    "word,both",
    [
        ("полны", {"пол-ны́", "по́л-ны"}),
        ("темны", {"тем-ны́", "тём-ны"}),
        ("бледны", {"бле́-дны", "бле-дны́"}),
    ],
)
def test_a_short_plural_adjective_has_both_stresses(word, both):
    w = line_words(word)[0]
    assert {w.sung(r.stress, mark=True) for r in w.readings} == both


def test_an_end_stressed_adjective_keeps_one_short_plural():
    assert {r.stress for r in line_words("больны")[0].readings} == {1}


def test_lermontov_scans():
    report = scan(
        "Тихие долины\nПолны свежей мглой;\n",
        from_dict({"language": "ru", "meter": "trochee", "feet": 3}),
    )
    assert all(lr.ok for lr in report.lines)


@pytest.mark.parametrize("word", ["Алма-Ата", "Улан-Удэ", "Д'Артаньян"])
def test_a_capital_opening_a_name_part_is_no_stress_mark(word):
    w = line_words(word)[0]
    assert all(r.source != "mark" for r in w.readings)


def test_a_capital_inside_a_word_still_marks_the_stress():
    assert line_words("замОк")[0].readings[0].stress == 1


@pytest.mark.parametrize(
    "text,meter",
    [
        ("Вечерний звон, вечерний звон!\nКак много дум наводит он\n", "iamb"),
        (
            "Гой ты, Русь, моя родная,\nХаты — в ризах образа...\n"
            "Не видать конца и края —\nТолько синь сосёт глаза.\n",
            "trochee",
        ),
    ],
)
def test_classics_with_fixed_rows_scan(text, meter):
    report = scan(
        text,
        from_dict(
            {
                "language": "ru",
                "meter": meter,
                "feet": 4,
                "rhyme": "AA" if text.count("\n") == 2 else "ABAB",
            }
        ),
    )
    assert all(lr.ok for lr in report.lines), [i.message for i in report.issues]


@pytest.mark.parametrize(
    "line,word,stress",
    [
        ("Смотрю на тени на стене", "тени", {0, 1}),
        ("Как на духу тебе скажу", "духу", {1}),
        ("Сгорело всё на корню", "корню", {1}),
    ],
)
def test_locative_and_accusative_after_na(line, word, stress):
    w = next(w for w in line_words(line) if w.norm == word)
    assert {r.stress for r in w.readings} == stress


def test_the_count_form_after_a_small_number():
    w = next(w for w in line_words("Я сделал четыре шага") if w.norm == "шага")
    assert [r.stress for r in w.readings] == [1]
    w = next(w for w in line_words("От часа до утра") if w.norm == "часа")
    assert 0 in {r.stress for r in w.readings}


def test_ukrainian_letters_are_counted_and_named():
    report = scan("Я пою тебе: ніч і їжак\n", from_dict({"language": "ru"}))
    assert report.lines[0].fit.count == 9
    assert any("not Armenian, Russian or English" in i.message for i in report.issues)


def test_a_stanza_whose_meter_is_dropped_is_named():
    from ashugh.translate import derive_spec

    text = (
        "Мой дядя самых честных правил\nКогда не в шутку занемог\n"
        "Он уважать себя заставил\nИ лучше выдумать не мог\nСкучно сидеть с ним день и ночь\n"
    )
    notes: list[str] = []
    data = derive_spec(scan(text), {"syllables", "meter"}, notes)
    assert "meter" not in data["stanza"]["1"]
    assert notes == [
        "stanza 1: iamb not kept, as L5 is off its beat; mark the stress or fix the line"
    ]


@pytest.mark.parametrize(
    "line,out",
    [
        ("Все прошло, все миновало,", "Всё прошло, всё миновало,"),
        ("Все равно", "Всё равно"),
        ("Все люди спят", "Все люди спят"),
    ],
)
def test_vsyo_is_restored_where_it_can_only_be_vsyo(line, out):
    assert sung(line).splitlines()[-1] == out


def test_acute_mode_turns_the_writers_capital_into_an_acute():
    assert sung("Открой замОк", stress="acute").splitlines()[-1] == "Открой замо́к"


def test_a_rejected_candidate_names_its_count_first():
    from ashugh.fit import fit_song
    from ashugh.proposers import StaticProposer

    text = "Мороз и солнце день чудесный\nЕщё ты спишь\n"
    spec = from_dict({"language": "ru", "meter": "iamb", "feet": 4, "rhyme": "AA"})
    result = fit_song(text, spec, StaticProposer({2: ["Пусть в речке стынет вода"]}), rounds=1)
    (why,) = [r["why"] for u in result.unresolved for r in u.rejected]
    assert why.startswith("3 feet, slot is 4") and "off the beat" in why


@pytest.mark.parametrize(
    "line", ["Любовь, разлука и т.д.", "Мы шли по пр. Мира", "Живу на ул. Ленина"]
)
def test_a_dotted_abbreviation_is_named(line):
    report = scan(line + "\n", from_dict({"language": "ru"}))
    assert any(i.message == "an abbreviation is sung in full" for i in report.issues)


@pytest.mark.parametrize("line", ["Я жду тебя. Ты придёшь", "Сам. Один", "Он ушёл в лес."])
def test_a_sentence_end_is_no_abbreviation(line):
    report = scan(line + "\n", from_dict({"language": "ru"}))
    assert not any(i.message == "an abbreviation is sung in full" for i in report.issues)


def test_the_hyphenated_post_chorus_tag_is_named():
    out = suno.format_song("[Пост-припев]\nЛа-ла-ла\n").text
    assert "[Post-Chorus]" in out


@pytest.mark.parametrize(
    "word,shown",
    [
        ("кручинушка", "кру-чи́-ну-шка"), ("сторонушка", "сто-ро́-ну-шка"), ("Онегин", "О-не́-гин"),
        ("Гагарин", "Га-га́-рин"), ("оне", "о-не́"), ("нея", "не-я́"), ("подушка", "по-ду́-шка"),
    ],
)  # fmt: skip
def test_folk_diminutives_surnames_and_old_pronouns(word, shown):
    assert first(word) == shown
