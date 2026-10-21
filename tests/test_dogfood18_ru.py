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


@pytest.mark.parametrize(
    "line,norm,shown",
    [
        ("Звездою севера явись", "севера", "се́-ве-ра"),
        ("Увяданья золотом охваченный", "золотом", "зо́-ло-том"),
        ("Я иду по тропе одна", "тропе", "тро-пе́"),
        ("Взмах крыла", "крыла", "кры-ла́"),
    ],
)
def test_the_everyday_reading_comes_first(line, norm, shown):
    assert first(line, norm) == shown


def test_v_pole_has_no_rare_pole():
    assert stresses("Белая в поле стоишь", "поле") == {0}


@pytest.mark.parametrize(
    "line",
    [
        "Это было в сорок первом году",
        "в двадцать первом веку",
        "в тысяча девятьсот сорок пятом году",
    ],
)
def test_a_second_locative_past_a_numeral(line):
    w = line_words(line)[-1]
    assert {r.stress for r in w.readings} == {1}


def test_a_repeated_line_gets_its_first_copys_best_attempt():
    from ashugh import translate

    class Bank:
        name = "bank"

        def propose(self, requests):
            return {r.id: ["Lyuli, lyuli, standing"] for r in requests if r.line == 1}

    text = "Люли, люли, стояла,\nЛюли, люли, стояла,\n"
    result = translate.translate_song(text, "en", Bank(), keep={"syllables"}, rounds=1)
    assert "Люли" not in result.text
    assert result.text.count("Lyuli, lyuli, standing") == 2


@pytest.mark.parametrize(
    "line,norm,shown",
    [
        ("Иван Иванович", "иванович", "И-ва́-но-вич"),
        ("Мария Ивановна", "ивановна", "И-ва́-но-вна"),
        ("Юрий Юрьевич", "юрьевич", "Ю́-рье-вич"),
        ("Наталья Павловна", "павловна", "Па́-вло-вна"),
        ("Иван Михайлович", "михайлович", "Ми-ха́й-ло-вич"),
        ("Сергей Дмитриевич", "дмитриевич", "Дми́-три-е-вич"),
        ("Владимир Ильич", "ильич", "И-льи́ч"),
        ("Владимира Ильича", "ильича", "И-льи-ча́"),
        ("Пётр Петрович", "петрович", "Пе-тро́-вич"),
    ],
)
def test_patronymics_keep_their_names_stress(line, norm, shown):
    assert first(line, norm) == shown


@pytest.mark.parametrize(
    "word,shown",
    [("заломати", "за-ло-ма́-ти"), ("гуляти", "гу-ля́-ти"), ("кудряву", "ку-дря́-ву")],
)
def test_folk_forms_take_their_words_stress(word, shown):
    assert first(word, word) == shown
    assert not word_guessed(word)


def word_guessed(norm: str) -> bool:
    return word(norm, norm).guessed


def test_the_folk_song_derives_feminine_endings():
    from ashugh import translate

    text = (
        "Во поле берёза стояла,\nНекому берёзу заломати,\n"
        "Некому кудряву заломати,\nЛюли, люли, заломати.\n"
    )
    data = translate.derive_spec(scan(text, Spec(language="ru")), keep={"endings"})
    assert data["stanza"]["1"]["endings"] == "ffff"


@pytest.mark.parametrize(
    "word,shown",
    [
        ("пятидесяти", "пя-ти́-де-ся-ти"),
        ("шестьюдесятью", "шес-тью́-де-ся-тью"),
        ("пятистам", "пя-ти-ста́м"),
        ("тремястами", "тре-мя-ста́-ми"),
        ("двухсот", "двух-со́т"),
        ("обе", "о́-бе"),
        ("езды", "е-зды́"),
    ],
)
def test_numeral_cases_and_missing_words(word, shown):
    assert first(word, word) == shown and not word_guessed(word)


@pytest.mark.parametrize("name,shown", [("Маруся", "Ма-ру́-ся"), ("Катюша", "Ка-тю́-ша")])
def test_folk_diminutive_names(name, shown):
    assert first(f"Я люблю {name}", name.lower()) == shown


@pytest.mark.parametrize(
    "line,out",
    [("Темным-темно в лесу ночном", "Тёмным-темно"), ("Желто-зеленый лист", "Жёлто-зелёный")],
)
def test_a_hyphenated_compound_keeps_each_parts_yo(line, out):
    assert sung(line).startswith(out)


def test_spec_from_warns_of_guessed_stresses():
    from ashugh import translate

    report = scan("Мы пели о кшвыре\nИ шли домой\n", Spec(language="ru"))
    warnings = translate.source_warnings(report)
    assert any("guessed stress" in w and "кшвыре" in w for w in warnings)


def test_syl_marks_a_stress_moved_onto_the_preposition(capsys):
    from ashugh.cli import main

    main(["syl", "--meter", "dactyl", "Взял меня за руку вывел за дверь"])
    assert "за́ ру-ку" in capsys.readouterr().out


@pytest.mark.parametrize("line,out", [("Не был я там", "Не́ был"), ("По полю гуляю", "По")])
def test_suno_never_writes_a_short_word_in_capitals(line, out):
    text = sung(line)
    assert text.startswith(out) and not text.split()[0].isupper()


def test_probe_makes_one_set_for_one_word_written_two_ways():
    from ashugh import probe

    plan = probe.make_probes(["замо́к", "замОк"], "ru")
    assert len({p.lyrics for p in plan}) == len(plan) == 3
    assert all(p.sung == p.sung.lower() for p in plan)


@pytest.mark.parametrize("a,b", [("голландцы", "танцы"), ("агентство", "блаженство")])
def test_silent_consonants_of_ndts_and_ntstv(a, b):
    assert rhyme.score(*_tails(a, b)) >= rhyme.THRESHOLD["perfect"]


def _tails(a: str, b: str):
    from ashugh import meter

    lines = analyze_lines(f"{a}\n{b}", Spec(language="ru"))
    return [rhyme.tails(ln, meter.fit(ln.words, "free"))[0] for ln in lines]


@pytest.mark.parametrize(
    "word,shown", [("изи", "и́-зи"), ("лайкни", "лай-кни́"), ("аккаунт", "ак-ка́-унт")]
)
def test_slang_of_todays_songs(word, shown):
    assert first(word, word) == shown
