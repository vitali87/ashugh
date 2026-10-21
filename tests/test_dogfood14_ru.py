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


@pytest.mark.parametrize(
    "phrase, stress",
    [
        ("свет из окна", 1),
        ("ты ждёшь у окна", 1),
        ("с утра до ночи", 1),
        ("до утра не спится", 1),
        ("я уехал из страны", 1),
        ("я летел до луны", 1),
        ("ждала у сосны", 1),
        ("свет от свечи", 1),
        ("нет ни души", 1),
        ("вдали от семьи", 1),
        ("без письма", 1),
        ("пьяный от вина", 1),
        ("я пришёл из села", 1),
        ("из гнезда", 1),
    ],
)
def test_after_a_genitive_preposition_the_noun_is_no_plural(phrase, stress):
    words = line_words(phrase)
    k = next(i for i, w in enumerate(words) if i and words[i - 1].norm in ru.GENITIVE_PREPOSITIONS)
    r = words[k].readings[0]
    assert r.stress == stress and "ё" not in r.spelling


@pytest.mark.parametrize("phrase", ["вижу окна", "в окна", "мои сёла", "за окна"])
def test_elsewhere_the_plural_stays(phrase):
    w = line_words(phrase)[-1]
    assert 0 in {r.stress for r in w.readings}


def test_suno_writes_the_genitive():
    out = suno.format_song("Свет из окна, я пришёл из села\n", tags=False).text
    assert "из окна," in out and "из села" in out  # unambiguous now: no mark needed


def test_an_anapest_with_utra_is_detected():
    rep = scan("Я гуляю с утра до утра\n", from_dict({"language": "ru"}))
    assert rep.units[0].meter.startswith("anapest")


@pytest.mark.parametrize(
    "word, value, stress",
    [("по-моему", "по-мо́ему", 1), ("жил-был", "жи́л-был", 0), ("тра-та-та", "тра́-та-та", 0)],
)
def test_a_hyphenated_word_can_be_put_in_the_lexicon(word, value, stress):
    assert ru.override_error(word, value) is None
    (ln,) = analyze_lines(word, Spec(language="ru", lexicon={word: value}))
    assert ln.words[0].readings[0].stress == stress


def test_a_lexicon_value_spelling_another_word_is_still_refused():
    assert ru.override_error("по-моему", "по-тво́ему") is not None


@pytest.mark.parametrize(
    "word, stress",
    [
        ("дабы", 0),
        ("дождусь", 1),
        ("дождешься", 1),
        ("дождётся", 1),
        ("дождутся", 1),
        ("посреди", 2),
    ],
)
def test_dictionary_gaps_and_errors(word, stress):
    w = ru.analyze_word(word)
    assert w.readings[0].stress == stress and not w.guessed


@pytest.mark.parametrize(
    "tag, out",
    [
        ("[Пред-припев]", "[Pre-Chorus]"),
        ("[Переход]", "[Bridge]"),
        ("[Гитарное соло]", "[Guitar Solo]"),
    ],
)
def test_more_russian_tags(tag, out):
    from ashugh import lyrics

    assert lyrics.retag(tag) == out


@pytest.mark.parametrize("token, stress", [("замо'к", 1), ("за'мок", 0), ("Мо'ре", 0)])
def test_an_apostrophe_after_a_vowel_marks_the_stress(token, stress):
    w = ru.analyze_word(token)
    assert w.readings[0].stress == stress and w.readings[0].source == "mark"
    assert w.size == 2


@pytest.mark.parametrize("stress, out", [("caps", "замОк"), ("acute", "замо́к")])
def test_suno_reads_an_apostrophe_mark_as_the_writers_stress(stress, out):
    text = suno.format_song("Висит на воротах замо'к\n", tags=False, stress=stress).text
    assert out in text and "'" not in text


@pytest.mark.parametrize(
    "line, meter_name",
    [("Жил-был у бабушки серенький козлик", "dactyl"), ("Жил-был ёжик у реки", "trochee4")],
)
def test_a_pair_of_one_syllable_words_may_lend_either_its_beat(line, meter_name):
    rep = scan(line + "\n", from_dict({"language": "ru", "meter": meter_name}))
    assert rep.ok, [i.message for i in rep.issues if i.severity == "error"]


def test_zhil_byl_reads_zhil_first():
    assert [r.stress for r in ru.analyze_word("жил-был").readings] == [0, 1]


def test_longer_parts_keep_the_last_parts_stress():
    assert ru.analyze_word("давным-давно").readings[0].stress == 3


@pytest.mark.parametrize(
    "text, size",
    [
        ("Ветер мѝлый, вѐтер", 6),
        ("сѐверо-за́падный ветер", 8),
        ("Висит на воротах за̀мок", 8),
    ],
)
def test_a_grave_accent_marks_a_stress_and_loses_nothing(text, size):
    (ln,) = analyze_lines(text, Spec(language="ru"))
    assert sum(w.size for w in ln.words) == size


def test_a_grave_on_a_vowel_is_the_writers_stress():
    (ln,) = analyze_lines("Висит на воротах за̀мок", Spec(language="ru"))
    w = ln.words[-1]
    assert w.text.replace("́", "") == "замок" and w.readings[0].stress == 0


@pytest.mark.parametrize(
    "word, pieces",
    [
        ("Тверской", "Твер-ской"),
        ("вёрсты", "вёр-сты"),
        ("мартовский", "мар-тов-ский"),
        ("членских", "член-ских"),
        ("честных", "чест-ных"),  # тн begins no syllable
        ("центра", "цен-тра"),
    ],
)
def test_s_and_a_stop_begin_the_syllable_after_a_consonant(word, pieces):
    assert "-".join(ru.split_syllables(word)) == pieces


def test_suno_writes_the_yo_the_rhyme_chose():
    out = suno.format_song(
        "Ты так красиво поешь,\nЧто сердце моё найдёшь.\n", stress="none", tags=False
    )
    assert out.text.splitlines()[0] == "Ты так красиво поёшь,"
    assert any(n.kind == "yo" and n.new == "поёшь" for n in out.notes)


def test_suno_keeps_the_e_when_the_rhyme_wants_it():
    out = suno.format_song("Ты так красиво поешь,\nА я пою: ешь!\n", stress="none", tags=False)
    assert out.text.splitlines()[0] == "Ты так красиво поешь,"


def test_suno_leaves_an_unrhymed_homograph_alone():
    out = suno.format_song("Ты так красиво поешь\n", stress="none", tags=False)
    assert out.text.splitlines()[0] == "Ты так красиво поешь"


def test_suno_rhymed_spelling_with_two_equal_partners():
    text = "Ты так красиво поешь,\nТы всё равно найдёшь,\nИ ты меня поймёшь.\n"
    out = suno.format_song(text, stress="none", tags=False)
    assert out.text.splitlines()[0] == "Ты так красиво поёшь,"


@pytest.mark.parametrize(
    "line,size,stress",
    [
        ("в TikTok'е", 3, 1),  # тик-то́-ке
        ("в Instagram'е", 4, 2),  # ин-ста-гра́-ме
        ("в iPhone'а", 3, 1),  # ай-фо́-на
        ("на YouTube'е", 3, 1),  # ю-ту́-бе
        ("в TikTok-е", 3, 1),
        ("Instagram-ы", 4, 2),
        ("Instagram-ами", 5, 2),
        ("в Google'е", 2, 0),  # гу́г-ле: the English syllabic l is no syllable before a vowel
        ("в Netflix'е", 3, 0),  # не́т-флик-се
    ],
)
def test_latin_brand_with_a_russian_ending(line, size, stress):
    w = line_words(line)[-1]
    assert w.lang == "ru"
    assert w.size == size
    assert w.readings[0].stress == stress


def test_latin_brand_with_a_russian_ending_scans_in_a_russian_line():
    report = scan("Мы танцуем в TikTok-е до утра\n", Spec(language="ru"))
    (lr,) = report.lines
    assert lr.line.lang == "ru"
    assert sum(w.size for w in lr.line.words) == 10


def test_latin_brand_with_a_russian_ending_survives_suno():
    out = suno.format_song("Я листаю Instagram'е ночами\n", tags=False)
    assert "Instagram'е" in out.text
    out = suno.format_song("Я листаю Instagram'е ночами\n", tags=False, split="all")
    assert "In-sta-gram-'е" in out.text


def test_a_latin_word_with_an_apostrophe_s_is_still_english():
    w = line_words("Mary's")[-1]
    assert w.lang == "en"


@pytest.mark.parametrize(
    "a,b,floor",
    [
        ("ты мой star", "гитар", 0.9),
        ("okay", "окей", 0.9),
        ("baby", "бейби", 0.7),
        ("in the sky", "дай", 0.9),
        ("go", "далеко", 0.7),
        ("my love", "кровь", 0.0),  # ʌ is а: no rhyme with о
    ],
)
def test_rhymes_across_english_and_russian(a, b, floor):
    s = rhymes(a, b)
    assert s >= floor
    if floor == 0.0:
        assert s < 0.45


def test_go_and_daleko_score_as_russian_go_and_ko_would():
    assert rhymes("go", "далеко") == rhymes("ого", "далеко")


def test_latin_brand_with_a_russian_ending_rhymes_in_russian():
    assert rhymes("в TikTok'е", "в потоке") >= 0.7
    assert rhymes("в Instagram'е", "в программе") >= 0.7


def test_english_rhymes_are_unchanged_by_the_adaptation():
    assert rhymes("star", "far") >= 0.9
    assert rhymes("sky", "die") >= 0.9
