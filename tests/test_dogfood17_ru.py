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
