"""Round 15 of dogfooding, Russian: what a songwriter found wrong."""

import pytest

from ashugh import meter, rhyme, suno
from ashugh.scan import analyze_lines, scan
from ashugh.spec import Spec, from_dict


def line_words(line: str):
    (ln,) = analyze_lines(line, Spec(language="ru"))
    return ln.words


def rhymes(a: str, b: str) -> float:
    lines = analyze_lines(f"{a}\n{b}", Spec(language="ru"))
    return rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))[0]


def sung(text: str, **kw) -> str:
    return suno.format_song(text, tags=False, **kw).text


@pytest.mark.parametrize("a,b", [("сел", "ушёл"), ("лес", "пёс"), ("лет", "полёт")])
def test_a_rare_yo_twin_of_a_short_word_is_no_reading(a, b):
    assert rhymes(a, b) < 0.45


@pytest.mark.parametrize(
    "a,b", [("без слез", "грёз"), ("обо всем", "моём"), ("ну и черт", "упёрт")]
)
def test_a_real_yo_twin_still_rhymes(a, b):
    assert rhymes(a, b) >= 0.9


def test_vse_keeps_both_readings():
    assert {r.spelling for r in line_words("все")[0].readings} == {"все", "всё"}


@pytest.mark.parametrize(
    "text,word",
    [
        ("Прошло так много лет,\nИ вот он, мой полёт.\n", "лет"),
        ("Шумит над нами тёмный лес.\n", "лес"),
    ],
)
def test_suno_leaves_a_short_word_alone(text, word):
    first = sung(text).splitlines()[0]
    assert first == text.splitlines()[0]


@pytest.mark.parametrize(
    "word,stress",
    [
        ("уходя", 2), ("приходя", 2), ("входя", 1), ("отходя", 2), ("нося", 1), ("водя", 1),
        ("ходя", 1), ("летя", 1), ("следя", 1), ("бродя", 1), ("гася", 1), ("возя", 1),
        ("уводя", 2), ("идя", 1), ("неся", 1), ("теряя", 1), ("видя", 0),
    ],
)  # fmt: skip
def test_a_gerund_takes_its_verbs_stress_not_a_nouns(word, stress):
    assert line_words(word)[0].readings[0].stress == stress


def test_pushkin_otkhodya_scans():
    report = scan(
        "Не отходя ни шагу прочь!\n", from_dict({"language": "ru", "meter": "iamb", "feet": 4})
    )
    assert report.lines[0].ok, report.lines[0].issues


@pytest.mark.parametrize(
    "word,stress",
    [("выхожу", 2), ("выношу", 2), ("выходили", 2), ("выводи", 2)],
)
def test_a_vy_verb_reads_as_the_usual_imperfective_first(word, stress):
    assert line_words(word)[0].readings[0].stress == stress


@pytest.mark.parametrize("word", ["выйти", "выход", "выбрать"])
def test_a_vy_word_with_one_reading_keeps_it(word):
    assert line_words(word)[0].readings[0].stress == 0


def test_suno_leaves_lermontov_alone():
    assert sung("Выхожу один я на дорогу\n").startswith("ВыхожУ")  # not ВЫхожу


@pytest.mark.parametrize("word,stress", [("соловей", 2), ("целей", 0), ("бурей", 0), ("шалей", 0)])
def test_an_ej_word_takes_no_comparative_it_does_not_have(word, stress):
    assert {r.stress for r in line_words(word)[0].readings} == {stress}


@pytest.mark.parametrize("word,stress", [("милей", 1), ("сильней", 1), ("веселей", 2)])
def test_a_real_short_comparative_keeps_its_stress(word, stress):
    assert stress in {r.stress for r in line_words(word)[0].readings}


def test_suno_sings_a_nightingale():
    assert sung("Пой, соловей, пой\n").strip() == "Пой, соловей, пой"


@pytest.mark.parametrize("pronoun", ["тебе", "себе", "нашем", "вашем"])
def test_more_pronouns_may_take_a_weak_beat(pronoun):
    assert line_words(pronoun)[0].weak


def test_yesenin_tebe_scans():
    spec = from_dict({"language": "ru", "meter": "anapest", "feet": 3})
    report = scan("Я готов рассказать тебе поле\n", spec)
    assert report.lines[0].ok, report.lines[0].issues


@pytest.mark.parametrize("word,stress", [("замученный", 1), ("купленный", 0), ("провален", 1)])
def test_a_mobile_verbs_participle_reads_stem_stressed_first(word, stress):
    # the end-stressed twin stays second: poetry has погружённый and искуплён too
    assert line_words(word)[0].readings[0].stress == stress


@pytest.mark.parametrize("word", ["обо", "ото", "безо", "предо"])
def test_a_two_syllable_preposition_is_known_and_unstressed(word):
    w = line_words(word + " мне")[0]
    assert w.clitic or w.weak
    assert not w.guessed


def test_suno_leaves_obo_unmarked():
    assert "обо мне" in sung("Загрустила шибко обо мне\n")


@pytest.mark.parametrize("phrase", ["на Дону", "в Крыму", "Казаки на Дону"])
def test_a_place_takes_its_stressed_locative(phrase):
    w = line_words(phrase)[-1]
    assert w.readings[0].stress == 1 and len({r.stress for r in w.readings}) == 1


def test_a_hyphenated_place_ends_on_its_locative():
    w = line_words("Я из Ростова-на-Дону")[-1]
    assert w.readings[0].stress == w.size - 1


def test_suno_leaves_krymu_alone():
    assert "в Крыму" in sung("Мы встретились в Крыму\n")


def test_tikho_na_donu_scans():
    report = scan(
        "Тихо-тихо на Дону\n", from_dict({"language": "ru", "meter": "trochee", "feet": 4})
    )
    assert report.lines[0].ok, report.lines[0].issues


@pytest.mark.parametrize(
    "word,stress",
    [("полчаса", 2), ("утраченный", 1), ("полжизни", 1), ("трёхсот", 1), ("трехсот", 1)],
)
def test_dictionary_slips_are_corrected(word, stress):
    assert line_words(word)[0].readings[0].stress == stress


def test_polchasa_couplet_passes():
    text = "Прошло всего лишь полчаса,\nА я забыл твои глаза.\n"
    report = scan(text, from_dict({"language": "ru", "meter": "iamb", "feet": 4, "rhyme": "AA"}))
    assert report.ok, report.issues


def test_a_section_of_backing_vocals_only_is_still_a_section():
    text = "[Intro]\n(О-о-о)\n\n[Verse]\nМы выходили в ночь\n"
    report = scan(text, from_dict({"language": "ru", "section": {"intro": {"meter": "free"}}}))
    assert not any("matches no section" in i.message for i in report.issues)


def test_a_section_the_song_lacks_is_still_warned():
    text = "[Verse]\nМы выходили в ночь\n"
    report = scan(text, from_dict({"language": "ru", "section": {"intro": {"meter": "free"}}}))
    assert any("matches no section" in i.message for i in report.issues)


@pytest.mark.parametrize(
    "word,split",
    [
        ("объятья", "объ-я-тья"), ("подъезд", "подъ-езд"), ("счастье", "счас-тье"),
        ("семья", "се-мья"), ("вьюга", "вью-га"), ("съесть", "съесть"), ("разъезд", "разъ-езд"),
    ],
)  # fmt: skip
def test_no_syllable_starts_with_a_hard_or_soft_sign(word, split):
    from ashugh.lang import ru

    assert "-".join(ru.split_syllables(word)) == split


@pytest.mark.parametrize("line", ["Жил-был у бабушки серенький козлик", "Раз-два-три, замри"])
def test_suno_marks_no_stress_in_a_chain_of_short_words(line):
    out = sung(line + "\n")
    assert out.strip() == line
