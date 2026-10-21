"""Round 17 of dogfooding, Russian: what a songwriter found wrong."""

import pytest

from ashugh import meter, rhyme, suno
from ashugh.scan import analyze_lines, scan
from ashugh.spec import Spec, from_dict


def line_words(line: str):
    (ln,) = analyze_lines(line, Spec(language="ru"))
    return ln.words


def first(word: str) -> str:
    w = line_words(word)[0]
    return w.sung(w.readings[0].stress, mark=True)


def stresses(line: str, word: str) -> set[int]:
    w = next(w for w in line_words(line) if w.norm == word)
    return {r.stress for r in w.readings}


def rhymes(a: str, b: str) -> float:
    lines = analyze_lines(f"{a}\n{b}", Spec(language="ru"))
    return rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))[0]


def sung(text: str, **kw) -> str:
    return suno.format_song(text, tags=False, **kw).text


@pytest.mark.parametrize("word", ["колей", "солей", "кисей", "ворожей"])
def test_a_word_in_ei_beside_a_noun_in_ee_does_not_crash(word):
    report = scan(f"Не выбираясь из {word}\nМы шли среди пустых полей\n", Spec(language="ru"))
    assert len(report.lines) == 2
    w = line_words(word)[0]
    assert all(r.stress == w.size - 1 for r in w.readings)  # коле́й, ворожей on its end


def test_a_comparative_in_ei_keeps_its_stress():
    assert 1 in {r.stress for r in line_words("милей")[0].readings}
    assert {r.stress for r in line_words("сильней")[0].readings} == {1}


def test_veshchei_is_not_read_twice():
    stress = [r.stress for r in line_words("вещей")[0].readings]
    assert len(stress) == len(set(stress))


@pytest.mark.parametrize(
    "line,out",
    [
        ("Мы все вместе, мы семья,", "Мы все вместе, мы семья,"),
        ("Все тоже ушли домой,", "Все тоже ушли домой,"),
        ("Все давно ушли.", "Все давно ушли."),
        ("Все уже прошло", "Всё ужЕ прошло"),
        ("Все равно", "Всё равно"),
        ("Все лето", "Всё лето"),
    ],
)
def test_vse_before_an_adverb_waits_for_the_verb(line, out):
    assert sung(line).splitlines()[-1] == out


def test_vse_before_uzhe_and_a_plural_verb_stays_vse():
    assert not sung("Все уже спят, а я не сплю,").startswith("Всё")


@pytest.mark.parametrize(
    "word,shown",
    [
        ("полке", "по́л-ке"), ("пору", "по́-ру"), ("лета", "ле́-та"), ("рода", "ро́-да"),
        ("страстной", "стра́ст-ной"), ("морю", "мо́-рю"), ("солью", "со́-лью"),
        ("стрелки", "стре́л-ки"), ("полон", "по́-лон"), ("проводам", "про-во-да́м"),
    ],
)  # fmt: skip
def test_the_everyday_noun_form_comes_first(word, shown):
    assert first(word) == shown


@pytest.mark.parametrize(
    "line,word", [("И ты взяла меня на руки", "руки"), ("Упал под ноги", "ноги")]
)
def test_no_genitive_after_a_preposition_of_another_case(line, word):
    assert 1 not in stresses(line, word)  # ру́ки, or на́ руки with the stress shifted


def test_reki_and_na_ruki_do_not_rhyme():
    text = "Мы шли вдвоём вдоль той реки,\nИ ты взяла меня на руки.\n"
    assert any(
        i.code == "rhyme" for i in scan(text, from_dict({"language": "ru", "rhyme": "AA"})).issues
    )


def test_a_genitive_preposition_still_takes_the_end():
    assert stresses("У реки", "реки") == {1}


@pytest.mark.parametrize(
    "word,shown",
    [
        ("избегая", "и-збе-га́-я"), ("пропадая", "про-па-да́-я"), ("попадая", "по-па-да́-я"),
        ("нападая", "на-па-да́-я"), ("спеша", "спе-ша́"),
    ],
)  # fmt: skip
def test_a_gerund_takes_its_verbs_usual_stress(word, shown):
    assert first(word) == shown


@pytest.mark.parametrize(
    "line,word,stress",
    [
        ("Я у тебя в долгу", "долгу", 1),
        ("Я держу тебя на весу", "весу", 1),
        ("Это имя на слуху", "слуху", 1),
        ("Он работает в цеху", "цеху", 1),
        ("Он стрелял на скаку", "скаку", 1),
    ],
)
def test_more_second_locatives(line, word, stress):
    assert stresses(line, word) == {stress}


@pytest.mark.parametrize("line", ["Я верну тебе по долгу", "Не придавай весу словам"])
def test_no_second_locative_without_its_preposition(line):
    word = line.split()[-2] if "весу" in line else line.split()[-1]
    assert 0 in stresses(line, word)


def test_dolgu_rhymes_with_beregu():
    assert rhymes("Я у тебя в долгу", "Как лист на берегу") >= rhyme.THRESHOLD["perfect"]


@pytest.mark.parametrize("line", ["Глядя за реку", "Мы пошли на реку"])
def test_za_reku_shifts_onto_the_preposition(line):
    assert None in stresses(line, "реку")


def test_a_lexicon_key_with_yo_applies_to_the_word_written_with_e():
    spec = from_dict({"language": "ru", "lexicon": {"передохнём": "передохнём"}})
    (ln,) = analyze_lines("Передохнем, родная", spec)
    assert [r.source for r in ln.words[0].readings] == ["user"]
    assert ln.words[0].readings[0].spelling == "передохнём"


def test_a_lexicon_key_with_yo_does_not_reach_another_word():
    spec = from_dict({"language": "ru", "lexicon": {"всё": "всё"}})
    (ln,) = analyze_lines("Мы шли домой", spec)
    assert all(r.source != "user" for w in ln.words for r in w.readings)


@pytest.mark.parametrize("hum", ["Ммм", "Мм", "Хм", "Хмм", "Гм"])
def test_a_russian_hum_is_one_syllable(hum):
    (w, *_) = line_words(f"{hum}, как хорошо")
    assert w.size == 1


def test_a_hum_does_not_take_another_words_place():
    words = line_words("Ммм, как хорошо")
    assert [w.size for w in words] == [1, 1, 3]


@pytest.mark.parametrize(
    "word,shown",
    [
        ("второй", "вто-ро́й"),
        ("волна", "вол-на́"),
        ("волне", "вол-не́"),
        ("голубой", "го-лу-бо́й"),
        ("смогу", "смо-гу́"),
    ],
)
def test_no_second_reading_no_one_says(word, shown):
    assert len(line_words(word)[0].readings) == 1
    assert first(word) == shown


def test_volny_the_plural_keeps_its_stem_stress():
    assert first("волны") == "во́л-ны"


@pytest.mark.parametrize(
    "line,word,stress",
    [("Сгинул без вести", "вести", 0), ("Из пасти не уйти", "пасти", 0)],
)
def test_no_infinitive_after_a_preposition(line, word, stress):
    assert stress in stresses(line, word)
    assert 1 not in stresses(line, word)


def test_an_infinitive_stays_where_no_preposition_stands():
    assert 1 in stresses("Мне его вести домой", "вести")


@pytest.mark.parametrize(
    "word",
    ["Лос-Анджелес", "Сан-Франциско", "Улан-Удэ", "Рио-де-Жанейро"],
)
def test_foreign_place_names(word):
    w = line_words(word)[0]
    assert w.readings[0].source == "lexicon"
    assert not w.guessed


@pytest.mark.parametrize(
    "word,shown",
    [
        ("Лос-Анджелес", "Лос-А́н-дже-лес"),
        ("Сан-Франциско", "Сан-Фран-ци́-ско"),
        ("Улан-Удэ", "У-лан-У-дэ́"),
        ("Рио-де-Жанейро", "Ри-о-де-Жа-не́й-ро"),
    ],
)
def test_foreign_place_names_are_stressed_as_said(word, shown):
    assert first(word) == shown


def test_a_hyphenated_word_with_an_unknown_part_is_a_guess():
    w = line_words("Ква-Мбукодзе")[0]
    assert w.guessed
    report = scan("Мы летим в Ква-Мбукодзе\n", Spec(language="ru"))
    assert any("unknown" in i.message for i in report.lines[0].issues)


def test_a_hyphenated_word_of_known_parts_is_no_guess():
    assert not line_words("давным-давно")[0].guessed


@pytest.mark.parametrize(
    "word,shown",
    [
        ("спасенный", "спа-сён-ный"),
        ("унесенные", "у-не-сён-ны-е"),
        ("принесенный", "при-не-сён-ный"),
        ("приведенный", "при-ве-дён-ный"),
        ("обретенный", "о-бре-тён-ный"),
        ("переведенный", "пе-ре-ве-дён-ный"),
        ("вынесенный", "вы́-не-сен-ный"),
        ("привлеченный", "при-вле-чён-ный"),
    ],
)
def test_participles_of_sti_and_ch_verbs(word, shown):
    assert first(word) == shown
    assert not line_words(word)[0].guessed


def test_suno_restores_the_participles_yo():
    assert sung("Унесенные ветром, мы летим,").startswith("Унесённые")


@pytest.mark.parametrize(
    "word,shown",
    [("полночный", "пол-но́-чный"), ("оков", "о-ко́в"), ("цветки", "цвет-ки́"), ("колен", "ко-ле́н")],
)
def test_common_words_the_table_lacked(word, shown):
    assert first(word) == shown


@pytest.mark.parametrize("word", ["обав", "обавок", "об"])
def test_a_warning_keeps_its_colon_at_any_width(word):
    from ashugh import report

    out = report.text(scan(f"Я вырвусь из {word}\n", Spec(language="ru")))
    row = next((r for r in out.splitlines() if "unknown" in r), "")
    assert " :" not in row
    if row:
        assert "unknown: assumed" in row
