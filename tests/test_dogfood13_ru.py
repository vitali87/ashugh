"""Round 13 of dogfooding, Russian: what a songwriter found wrong."""

import pytest

from ashugh import meter, rhyme, suno
from ashugh.lang import ru
from ashugh.scan import analyze_lines, scan
from ashugh.spec import Spec, from_dict


def main_stress(word: str) -> int | None:
    return ru.analyze_word(word).readings[0].stress


@pytest.mark.parametrize(
    "word, stress",
    [
        ("чёрно-белый", 2),
        ("тёмно-синий", 2),
        ("жёлто-синий", 2),
        ("ёлочка-красавица", 4),
        ("трёхэтажный", 2),
        ("трёхцветный", 1),
        ("трехцветный", 1),
        ("четырёхэтажный", 4),
        ("трёхсотый", 1),
        ("трёхколёсный", 2),
        ("зелёный", 1),
        ("самолёт", 2),
    ],
)
def test_a_yo_in_an_earlier_part_is_no_main_stress(word, stress):
    assert main_stress(word) == stress


def rhymes(a: str, b: str) -> float:
    lines = analyze_lines(f"{a}\n{b}", Spec(language="ru"))
    return rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))[0]


@pytest.mark.parametrize("a, b", [("чёрно-белый", "смелый"), ("трёхцветный", "заветный")])
def test_compounds_with_yo_rhyme_on_their_last_part(a, b):
    assert rhymes(a, b) >= rhyme.THRESHOLD["near"]


@pytest.mark.parametrize(
    "line, meter_name",
    [
        ("Ехали по́ лесу долго", "dactyl"),
        ("Я там не́ был", "trochee"),
    ],
)
def test_a_writers_mark_on_a_preposition_or_ne_moves_the_stress(line, meter_name):
    rep = scan(line + "\n", from_dict({"language": "ru", "meter": meter_name}))
    assert rep.ok, [i.message for i in rep.issues]


def test_the_word_after_a_marked_preposition_leans_on_it():
    (ln,) = analyze_lines("Взял её за́ руку", Spec(language="ru"))
    assert [r.stress for r in ln.words[-1].readings] == [None]


@pytest.mark.parametrize("stress, out", [("caps", "зА руку"), ("acute", "за́ руку")])
def test_suno_keeps_a_writers_mark_on_a_preposition(stress, out):
    got = suno.format_song("Взял её за́ руку\n", tags=False, stress=stress).text
    assert out in got


def test_a_stress_the_writer_moved_is_no_ambiguity():
    rep = scan("Ехали по́ лесу долго\n", from_dict({"language": "ru", "meter": "dactyl"}))
    assert not [i for i in rep.issues if i.code == "stress"]


@pytest.mark.parametrize("phrase", ["не был", "не было", "не дал", "не жил"])
def test_ne_takes_the_stress_of_these_verbs_by_default(phrase):
    (ln,) = analyze_lines(phrase, Spec(language="ru"))
    assert ln.words[1].readings[0].stress is None  # не́ был


@pytest.mark.parametrize("phrase", ["не с кем", "не о чем", "не за что", "не к кому"])
def test_ne_before_a_preposition_and_a_pronoun_takes_the_stress(phrase):
    (ln,) = analyze_lines(phrase, Spec(language="ru"))
    f = meter.fit(ln.words, "free")
    assert f.stresses.get(0) == 0 and f.stresses.get(2) is None  # не́ о чем


@pytest.mark.parametrize("a, b", [("не с кем", "резким"), ("Я там не был", "Смотрю на небо")])
def test_ne_stressed_rhymes(a, b):
    assert rhymes(a, b) >= rhyme.THRESHOLD["slant"]


def test_a_word_in_capitals_marks_no_stress():
    (ln,) = analyze_lines("ПЛАТА ЗА ЛЕЧЕНЬЕ", Spec(language="ru"))
    assert ln.words[-1].readings[0].stress == 1


@pytest.mark.parametrize(
    "word, stress",
    [
        ("сумерках", 0),
        ("качелях", 1),
        ("ножницах", 0),
        ("джинсах", 0),
        ("кудрями", 1),
        ("обоих", 1),
        ("обеих", 1),
        ("обоими", 1),
        ("полторы", 2),
        ("полутора", 1),
    ],
)
def test_forms_the_dictionary_lacks(word, stress):
    w = ru.analyze_word(word)
    assert w.readings[0].stress == stress and not w.guessed


def test_perfume_and_spirits_are_both_readings_of_duhov():
    assert {r.stress for r in ru.analyze_word("духов").readings} == {0, 1}
    assert rhymes("твоих духов", "моих стихов") >= rhyme.THRESHOLD["near"]


@pytest.mark.parametrize(
    "phrase", ["в этом дыму", "в нашем саду", "на том берегу", "в густом лесу", "в моём саду"]
)
def test_the_second_locative_is_end_stressed_after_an_adjective_too(phrase):
    (ln,) = analyze_lines(phrase, Spec(language="ru"))
    w = ln.words[-1]
    assert [r.stress for r in w.readings] == [w.size - 1]


def test_a_noun_after_a_noun_in_om_is_left_alone():
    (ln,) = analyze_lines("в доме саду", Spec(language="ru"))
    assert len(ln.words[-1].readings) >= 1 and ln.words[-1].readings[0].source != "rule"


@pytest.mark.parametrize("phrase", ["у дома", "из леса", "до города", "для голоса", "от берега"])
def test_after_a_genitive_preposition_a_plural_in_a_is_no_reading(phrase):
    (ln,) = analyze_lines(phrase, Spec(language="ru"))
    w = ln.words[-1]
    assert w.size - 1 not in {r.stress for r in w.readings}


@pytest.mark.parametrize("phrase, stress", [("из окна", 1), ("у моря", 0)])
def test_other_words_after_a_genitive_preposition_are_genitives_too(phrase, stress):
    (ln,) = analyze_lines(phrase, Spec(language="ru"))
    assert ln.words[-1].readings[0].stress == stress  # окна́, мо́ря: not о́кна, моря́


def test_suno_hints_no_stress_the_line_still_fails_with():
    out = suno.format_song(
        "Сижу у дома на скамейке\n",
        tags=False,
        spec=from_dict({"language": "ru", "meter": "trochee"}),
    ).text
    assert "домА" not in out


@pytest.mark.parametrize(
    "phrase", ["у реки", "из воды", "до горы", "для души", "без головы", "от весны"]
)
def test_after_a_genitive_preposition_a_feminine_is_its_genitive(phrase):
    (ln,) = analyze_lines(phrase, Spec(language="ru"))
    w = ln.words[-1]
    assert {r.stress for r in w.readings} == {w.size - 1}


def test_suno_hints_the_usual_reading_in_a_line_that_fails_its_meter():
    spec = from_dict({"language": "ru", "meter": "iamb"})
    out = suno.format_song("Небо синее над рекой\n", tags=False, spec=spec).text
    assert "синЕе" not in out


ROMANCE = (
    "Не уходи, мой свет вечерний,\nЕщё не время расставаться,\n"
    "Пусть будет путь наш самый верный\nХранимым кругом нежных рук.\n"
)


def test_the_partner_that_fails_its_own_slot_is_the_one_blamed():
    rep = scan(ROMANCE, from_dict({"language": "ru", "meter": "iamb4", "rhyme": "AbAb"}))
    broken = [i.line for i in rep.issues if i.code == "rhyme"]
    assert broken == [2]


def test_requests_ask_the_failing_partner_to_rhyme_with_the_good_one():
    from ashugh.fit import requests_for

    reqs = requests_for(ROMANCE, from_dict({"language": "ru", "meter": "iamb4", "rhyme": "AbAb"}))
    by_line = {r.line: r for r in reqs}
    assert by_line[2].rhyme_with == ["рук"]


REFRAIN = (
    "Я помню ночи над рекою,\nСвечу и тени на стене,\n"
    "Как ты, склонившись над рекою,\nШептала что-то в тишине.\n"
)


def test_a_request_for_a_refrain_line_says_why():
    from ashugh.fit import requests_for

    reqs = requests_for(REFRAIN, from_dict({"language": "ru", "meter": "iamb4", "rhyme": "AbAb"}))
    assert any("refrain" in p for r in reqs for p in r.problems)


def test_pick_takes_a_candidate_that_ends_a_refrain():
    from ashugh.fit import fit_song
    from ashugh.proposers import StaticProposer

    proposer = StaticProposer({3: ["Как ты, прильнув ко мне щекою,"]})
    spec = from_dict({"language": "ru", "meter": "iamb4", "rhyme": "AbAb"})
    res = fit_song(REFRAIN, spec, proposer, rounds=1)
    assert res.text.splitlines()[2] == "Как ты, прильнув ко мне щекою,"


def test_a_ternary_line_too_long_for_its_feet_says_so():
    rep = scan(
        "Солнце глядит на нас, как огромное око\n",
        from_dict({"language": "ru", "meter": "dactyl4"}),
    )
    issues = {i.code: i for i in rep.issues if i.severity == "error"}
    assert "syllables" in issues and "has 11" in issues["syllables"].detail
    assert issues["meter"].detail.endswith("dactyl4 wants /xx/xx/xx/x")


def test_a_line_that_fits_its_feet_gets_no_length_error():
    rep = scan("Солнце глядит на огромное око\n", from_dict({"language": "ru", "meter": "dactyl4"}))
    assert rep.ok


@pytest.mark.parametrize(
    "a, b", [("ласковый", "сказочный"), ("ласково", "сказочно"), ("ласковый", "масленый")]
)
def test_dactylic_words_with_the_same_vowels_are_at_least_assonant(a, b):
    assert rhymes(a, b) >= rhyme.THRESHOLD["assonance"]


@pytest.mark.parametrize("a, b", [("ласковый", "ветреный"), ("сказочный", "бешеный")])
def test_dactylic_words_with_other_vowels_are_not(a, b):
    assert rhymes(a, b) < rhyme.THRESHOLD["assonance"]


@pytest.mark.parametrize(
    "word, pieces",
    [
        ("диджей", "ди-джей"),
        ("бюджет", "бю-джет"),
        ("менеджер", "ме-не-джер"),
        ("аджика", "а-джи-ка"),
        ("беззвучный", "без-зву-чный"),
        ("рассвет", "рас-свет"),
        ("касса", "кас-са"),
        ("трёхцветный", "трёх-цве-тный"),
        ("отцвела", "от-цве-ла"),
        ("честных", "чест-ных"),
        ("центра", "цен-тра"),
        ("карта", "кар-та"),
        # negative: под- is a prefix before ж, тв after a cluster stays, пк is no onset
        ("поджечь", "под-жечь"),
        ("надженный", "над-жен-ный"),
        ("чувство", "чувст-во"),
        ("группка", "групп-ка"),
    ],
)
def test_russian_words_are_cut_where_they_are_sung(word, pieces):
    assert "-".join(ru.split_syllables(word)) == pieces


@pytest.mark.parametrize(
    "word, stress",
    [
        ("бейби", 0),
        ("дедлайн", 1),
        ("дедлайны", 1),
        ("флексить", 0),
        ("флексишь", 0),
        ("флекшу", 0),
        ("хайплю", 0),
        ("хайповый", 0),
        ("хайповая", 0),
        ("суперзвезда", 3),
        ("тренде", 0),
        ("френды", 0),
        ("звездопад", 2),
        ("Китай", 1),
        ("Китае", 1),
        ("хейтеры", 0),
        ("кринжем", 0),
        ("зумеры", 0),
    ],
)
def test_slang_and_loanwords_of_songs_are_known(word, stress):
    w = ru.analyze_word(word)
    assert w.readings[0].stress == stress and not w.guessed


def test_a_slang_spelling_shared_by_two_forms_keeps_both():
    w = ru.analyze_word("суперзвезды")
    assert {r.stress for r in w.readings} == {2, 3}
    assert "суперзвёзды" in {r.spelling for r in w.readings}


def test_the_dictionary_still_wins_over_the_slang_table():
    assert [r.stress for r in ru.analyze_word("треку").readings] == [0]  # the table's


def test_suno_marks_a_loanword_where_it_is_said():
    out = suno.format_song("Бейби, ты мой единственный свет\n", tags=False).text
    assert "БейбИ" not in out


def word_in(line: str, k: int):
    (ln,) = analyze_lines(line, Spec(language="ru"))
    return ln.words[k]


@pytest.mark.parametrize(
    "line, k, size, stress",
    [
        ("Меня остановили из ГИБДД", 3, 5, 4),  # гэ-и-бэ-дэ-дэ́: no word ends on бдд
        ("Сдал ЕГЭ на сто", 1, 2, 1),  # е-гэ́: said as a word, stressed on the end
        ("Болею за ЦСКА", 2, 3, 2),  # цэ-эс-ка́
        ("ЦСКА", 0, 3, 2),
        ("Открыл ИП в июне", 1, 2, 1),  # и-пэ́
        ("ВСЕ ДОРОГИ ВЕДУТ В ГИБДД", 4, 5, 4),
    ],
)
def test_abbreviations_are_said_as_russians_say_them(line, k, size, stress):
    w = word_in(line, k)
    assert (w.size, w.readings[0].stress) == (size, stress)


@pytest.mark.parametrize(
    "line, k, size",
    [
        ("Моя СТРАНА", 1, 2),  # a word in capitals for emphasis is no abbreviation
        ("Это ГДЕ", 1, 1),
        ("ВО ПОЛЕ БЕРЁЗА", 0, 1),
        ("ОН ушёл", 0, 1),
        ("Пошли в ЗАГС", 2, 1),
        ("Поступил в ВУЗ", 2, 1),
        ("Блок НАТО", 1, 2),
    ],
)
def test_words_in_capitals_stay_words(line, k, size):
    assert word_in(line, k).size == size


def test_nato_keeps_its_own_stress():
    assert word_in("Блок НАТО", 1).readings[0].stress == 0


@pytest.mark.parametrize(
    "line, out",
    [
        ("Болею за ЦСКА", "цэ-эс-кА"),
        ("Улетаю в США", "сэ-шэ-а́"),  # a lone vowel takes an acute, not a capital
        ("Меня остановили из ГИБДД", "гэ-и-бэ-дэ-дЭ"),
        ("Открыл ИП в июне", "и-пЭ"),
    ],
)
def test_suno_writes_an_abbreviation_as_it_is_said(line, out):
    assert out in suno.format_song(line + "\n", tags=False).text


@pytest.mark.parametrize(
    "a, b, sound",
    [("он же", "тоже", "onʒə"), ("ты ли", "пыли", "ɨlʲɪ")],
)
def test_a_word_after_the_last_stress_is_said_reduced(a, b, sound):
    lines = analyze_lines(f"{a}\n{b}", Spec(language="ru"))
    ts = [rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines]
    score, x, _ = rhyme.match(*ts)
    assert x is not None and x.sound.endswith(sound)
    assert score >= rhyme.THRESHOLD["near"]


@pytest.mark.parametrize("word, sound", [("лёгкий", "xkʲ"), ("мягче", "xtʃ"), ("легко", "xk")])
def test_g_before_k_is_said_kh(word, sound):
    assert sound in "".join(ru.analyze_word(word).readings[0].phones)


def test_other_g_is_left_alone():
    assert "g" in "".join(ru.analyze_word("книга").readings[0].phones)


@pytest.mark.parametrize("line", ["Светит небо надо мной", "Надо мною тяготеет"])
def test_nado_before_me_keeps_its_stress_as_verse_marks_it(line):
    # RIFMA's hand-marked verse stresses на́до мной every time
    (ln,) = analyze_lines(line, Spec(language="ru"))
    w = next(w for w in ln.words if w.norm == "надо")
    assert w.readings[0].stress == 0


@pytest.mark.parametrize(
    "word, spelling",
    [
        ("Горбачев", "горбачёв"),
        ("Королев", "королёв"),
        ("Хрущев", "хрущёв"),
        ("Королева", "королёва"),
        ("Горбачевым", "горбачёвым"),
    ],
)
def test_surnames_written_without_their_yo_get_it(word, spelling):
    (ln,) = analyze_lines(f"Вспомнил {word}", Spec(language="ru"))
    r = ln.words[1].readings[0]
    assert r.spelling == spelling and r.stress == ru.vowel_count(spelling.split("ё")[0])


def tag_notes(text: str) -> list[str]:
    return [n.why for n in suno.format_song(text).notes if n.kind == "tag"]


def test_a_single_untagged_stanza_is_not_said_to_repeat():
    (why,) = tag_notes("Я иду по улице\nИ пою свою песню\n")
    assert "repeat" not in why and "verse" in why


def test_stanzas_that_do_not_repeat_are_said_to_be_verses():
    whys = tag_notes("la la la\nla la la\n\nno no no\nno no no\n")
    assert len(whys) == 2 and all("no stanza repeats" in w for w in whys)


def test_a_repeated_stanza_is_said_to_be_the_chorus():
    whys = tag_notes("la la la\n\nno no no\n\nla la la\n")
    assert whys[0] == "a stanza that comes back is the chorus"
    assert whys[1] == "a stanza that does not come back is a verse"


@pytest.mark.parametrize(
    "line, k", [("Я ЖДУ тебя", 1), ("Все эти ДНИ", 2), ("Мы ШЛИ домой", 1), ("ЖДИ меня", 0)]
)
def test_a_short_word_in_capitals_is_a_word(line, k):
    w = word_in(line, k)
    assert w.size == 1 and not w.spelled


@pytest.mark.parametrize("line, k", [("Работал на ЦРУ", 2), ("Я из США", 2)])
def test_abbreviations_the_dictionary_lists_are_still_spelt(line, k):
    assert word_in(line, k).spelled


@pytest.mark.parametrize(
    "line, k, size",
    [("Ооо", 0, 1), ("Аааа, моя любовь", 0, 1), ("О-о-о", 0, 3), ("ее", 0, 2)],  # её is two
)
def test_a_vowel_written_long_is_one_held_note(line, k, size):
    assert word_in(line, k).size == size


def test_an_armenian_vowel_written_long_is_one_held_note():
    (ln,) = analyze_lines("Օօօ", Spec(language="hy"))
    assert ln.words[0].size == 1


def test_suno_keeps_a_held_note_as_written():
    assert suno.format_song("Ооо, моя любовь\n", tags=False).text.startswith("Ооо,")


@pytest.mark.parametrize(
    "tag, out",
    [
        ("[Куплет 2 - Рэп]", "[Verse 2 - Rap]"),
        ("[Бридж: соло]", "[Bridge: Solo]"),
        ("[Припев (рэп)]", "[Chorus (Rap)]"),
        ("[Куплет 1 (тихо)]", "[Verse 1 (тихо)]"),  # a free note stays as written
        ("[Куплет 2 - тише и медленнее]", "[Verse 2 - тише и медленнее]"),
    ],
)
def test_a_note_that_names_a_section_is_named_as_suno_names_it(tag, out):
    from ashugh import lyrics

    assert lyrics.retag(tag) == out
