"""Round 18 of dogfooding, Russian: what a songwriter found wrong."""

import pytest

from ashugh import rhyme, suno
from ashugh.scan import analyze_lines, scan
from ashugh.spec import Spec, from_dict


def line_words(line: str):
    (ln,) = analyze_lines(line, Spec(language="ru"))
    return ln.words


def word(line: str, norm: str):
    return next(w for w in line_words(line) if w.norm == norm)


def first(line: str, norm: str) -> str:
    w = word(line, norm)
    return w.sung(w.readings[0].stress, mark=True)


def stresses(line: str, norm: str) -> set:
    return {r.stress for r in word(line, norm).readings}


def sung(text: str, **kw) -> str:
    return suno.format_song(text, tags=False, **kw).text


@pytest.mark.parametrize(
    "form,shown",
    [
        ("вложенный", "вло́-жен-ный"),
        ("восстановленный", "вос-ста-но́-влен-ный"),
        ("купленный", "ку́-плен-ный"),
        ("охваченный", "о-хва́-чен-ный"),
    ],
)
def test_no_invented_end_stressed_participle(form, shown):
    w = word(form, form)
    assert len(w.readings) == 1 and first(form, form) == shown
    assert all("ё" not in r.spelling for r in w.readings)


def test_a_verb_with_both_participles_keeps_both():
    assert {r.spelling for r in word("погруженный", "погруженный").readings} == {
        "погруженный",
        "погружённый",
    }


def test_vlozhennyi_does_not_rhyme_with_vlyublyonnyi():
    spec = from_dict({"language": "ru", "rhyme": "AA"})
    assert not scan("Мой перстень в руку вложенный\nИ я в тебя влюблённый\n", spec).ok


@pytest.mark.parametrize(
    "line,norm,stress",
    [
        ("Еду я по чистому полю", "полю", 0),
        ("Я ждала до самой зимы", "зимы", 1),
        ("Пью из чистой воды", "воды", 1),
        ("Он пришёл с той стороны", "стороны", 2),
        ("Положи на мои руки", "руки", 0),
    ],
)
def test_a_preposition_governs_past_its_adjective(line, norm, stress):
    assert stresses(line, norm) == {stress}


def test_a_verb_with_no_preposition_before_it_stays_possible():
    assert 1 in stresses("Я сам полю огород", "полю")  # полю́, I weed


@pytest.mark.parametrize(
    "line,norm,shown",
    [
        ("три слова", "слова", "сло́-ва"),
        ("два глаза", "глаза", "гла́-за"),
        ("два берега", "берега", "бе́-ре-га"),
        ("три окна", "окна", "о-кна́"),
        ("две звезды", "звезды", "зве-зды́"),
        ("три сестры", "сестры", "сес-тры́"),
        ("две руки", "руки", "ру́-ки"),
        ("два моря", "моря", "мо́-ря"),
    ],
)
def test_a_noun_after_two_three_four_takes_its_count_form(line, norm, shown):
    assert first(line, norm) == shown
    assert len(word(line, norm).readings) == 1


def test_the_plural_stays_without_a_number():
    assert len(word("Его слова", "слова").readings) == 2


@pytest.mark.parametrize(
    "line,out",
    [
        ("Все пройдёт, и все будет хорошо,", "Всё пройдёт, и всё будет хорошо,"),
        ("Все течёт,", "Всё течёт,"),
        ("Это все, что есть у нас,", "Это всё, что есть у нас,"),
        ("Все в порядке", "Всё в порядке"),
        ("Вот и все", "Вот и всё"),
    ],
)
def test_vse_before_a_singular_verb_or_in_set_phrases_is_vsyo(line, out):
    assert sung(line).splitlines()[0] == out


@pytest.mark.parametrize("line", ["Все спят", "Все говорят", "Мы все идем", "Все люди", "Это все"])
def test_vse_with_a_plural_stays(line):
    assert sung(line).startswith(line.split()[0])
    assert "всё" not in sung(line).lower()


@pytest.mark.parametrize(
    "line,out",
    [
        ("О чем ты думаешь", "О чём ты думаешь"),
        ("В нем столько света", "В нём столько света"),
        ("Во всем виновата я", "Во всём виновата я"),
        ("при чем тут я", "при чём тут я"),
    ],
)
def test_nyom_chyom_vsyom_after_a_preposition(line, out):
    assert sung(line).splitlines()[0] == out


@pytest.mark.parametrize("line", ["Лучше, чем вчера", "Я дал всем", "Мне не о чем"])
def test_chem_and_vsem_elsewhere_keep_their_e(line):
    assert "ё" not in sung(line)


def test_o_nyom_rhymes_with_ognyom():
    lines = analyze_lines("Я думаю о нем\nИ обожжён огнем", Spec(language="ru"))
    from ashugh import meter

    tails = [rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines]
    assert rhyme.match(*tails)[0] >= rhyme.THRESHOLD["perfect"]


@pytest.mark.parametrize(
    "text",
    [
        "Скажи мне тихо: да,\nОстанься навсегда,\n",
        "И всё не то, не то,\nНе нужен мне никто.\n",
    ],
)
def test_a_clitic_ending_the_line_takes_the_stress(text):
    assert scan(text, from_dict({"language": "ru", "meter": "iamb3", "rhyme": "AA"})).ok


@pytest.mark.parametrize("line,norm", [("Ты знаешь ли", "ли"), ("Скажи же", "же")])
def test_a_true_enclitic_at_the_end_still_leans(line, norm):
    assert word(line, norm).enclitic or word(line, norm).clitic


@pytest.mark.parametrize(
    "line,norm,shown",
    [
        ("Читал я Льва Толстого", "толстого", "Тол-сто́-го"),
        ("А Лев Толстой молчал", "толстой", "Тол-сто́й"),
        ("И маршал Жуков снова", "жуков", "Жу́-ков"),
        ("И Петров пришёл", "петров", "Пе-тро́в"),
        ("Я читаю Достоевского", "достоевского", "До-сто-е́в-ско-го"),
        ("С Шукшиным", "шукшиным", "Шук-ши́-ным"),
    ],
)
def test_surnames_take_their_own_stress(line, norm, shown):
    assert first(line, norm) == shown


@pytest.mark.parametrize("line,norm,shown", [("Он толстой книгой", "толстой", "то́л-стой")])
def test_a_common_word_written_small_keeps_its_own(line, norm, shown):
    assert first(line, norm) == shown
