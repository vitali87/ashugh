"""Round 16 of dogfooding, Armenian: what a songwriter found wrong."""

import pytest

from ashugh import meter, rhyme
from ashugh.scan import analyze_lines, scan
from ashugh.spec import Spec, from_dict


def words(line: str, lang: str = "hy"):
    (ln,) = analyze_lines(line, Spec(language=lang))
    return ln.words


def sung(word: str) -> str:
    return words(word)[0].sung()


def hy_rhyme(a: str, b: str) -> float:
    lines = analyze_lines(f"{a}\n{b}", Spec(language="hy"))
    return rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))[0]


@pytest.mark.parametrize(
    "word,shown",
    [
        ("չգնաց", "չը-գը-նաց"), ("չմնաց", "չը-մը-նաց"), ("չլսեց", "չը-լը-սեց"),
        ("չգրեց", "չը-գը-րեց"), ("չթռավ", "չը-թը-ռավ"), ("չգնալու", "չը-գը-նա-լու"),
        ("չմտածեց", "չը-մը-տա-ծեց"), ("չգնացի", "չը-գը-նա-ցի"),
    ],
)  # fmt: skip
def test_the_negative_keeps_its_stems_schwa_in_the_aorist_and_participle(word, shown):
    assert sung(word) == shown


@pytest.mark.parametrize(
    "word,shown",
    [
        ("կգտնեմ", "կը-գըտ-նեմ"), ("կմտնեմ", "կը-մըտ-նեմ"), ("չմտնես", "չը-մըտ-նես"),
        ("կկտրեմ", "կը-կըտ-րեմ"), ("կկպնեմ", "կը-կըպ-նեմ"), ("կգտնի", "կը-գըտ-նի"),
    ],
)  # fmt: skip
def test_a_prefix_before_a_three_consonant_stem_keeps_the_stems_schwa(word, shown):
    assert sung(word) == shown


@pytest.mark.parametrize(
    "word,shown",
    [
        ("կգրեմ", "կը-գը-րեմ"),
        ("կգրի", "կը-գը-րի"),
        ("կգրեիր", "կը-գը-րե-իր"),
        ("կկրեմ", "կը-կը-րեմ"),
    ],
)
def test_the_future_of_grel_and_krel(word, shown):
    assert sung(word) == shown


@pytest.mark.parametrize("word,shown", [("չնչին", "չըն-չին"), ("կծծի", "կըծ-ծի")])
def test_roots_that_only_look_prefixed_stay(word, shown):
    assert sung(word) == shown


@pytest.mark.parametrize(
    "word,shown",
    [
        ("անշնորհք", "ան-շը-նորհք"), ("անսխալ", "ան-սը-խալ"), ("անխռով", "ան-խը-ռով"),
        ("անգթություն", "ան-գը-թու-թյուն"), ("անխնա", "ան-խը-նա"), ("անսեր", "ան-սեր"),
    ],
)  # fmt: skip
def test_the_negative_an_keeps_its_roots_schwa(word, shown):
    assert sung(word) == shown


@pytest.mark.parametrize(
    "word,shown",
    [
        ("քսանչորս", "քը-սան-չորս"), ("երեսունչորս", "ե-րե-սուն-չորս"),
        ("քառասունչորս", "քա-ռա-սուն-չորս"), ("գերմարդ", "գեր-մարդ"), ("տասնչորս", "տաս-նը-չորս"),
    ],
)  # fmt: skip
def test_a_compound_numeral_takes_no_possessive_schwa(word, shown):
    assert sung(word) == shown


@pytest.mark.parametrize(
    "word,shown",
    [
        ("Աստուած", "Աստ-ված"), ("անցեալ", "ան-ցյալ"), ("ուրախութեամբ", "ու-րա-խու-թյամբ"),
        ("մանեակ", "մա-նյակ"), ("սեաւ", "սև"), ("հայեացք", "հա-յացք"), ("արուեստ", "ար-վեստ"),
        ("թիւ", "թիվ"), ("հաշիւ", "հա-շիվ"), ("հիմայ", "հի-մա"), ("կայ", "կա"), ("չկայ", "չը-կա"),
        ("յոյս", "հույս"), ("յետոյ", "հե-տո"), ("կեանք", "կյանք"), ("ձիւն", "ձյուն"),
    ],
)  # fmt: skip
def test_classical_spelling_is_read_reformed(word, shown):
    assert sung(word).lower() == shown.lower()


@pytest.mark.parametrize(
    "word,shown",
    [
        ("Կորեայում", "Կո-րե-ա-յում"), ("սեանս", "սե-անս"), ("Նեանդերթալ", "Նե-ան-դեր-թալ"),
        ("ռեալ", "ռե-ալ"), ("իդեալ", "ի-դե-ալ"), ("Նոյ", "Նոյ"), ("Նիկոլայ", "Նի-կո-լայ"),
        ("յուղ", "յուղ"), ("դուետ", "դու-ետ"),
    ],
)  # fmt: skip
def test_a_loan_or_name_is_not_read_as_classical(word, shown):
    assert sung(word) == shown


def test_a_classical_rhyme_rhymes_as_it_is_said():
    assert hy_rhyme("հիմայ", "Ռիմա") >= rhyme.THRESHOLD["perfect"]


def test_a_lexicon_entry_may_give_a_classical_word_its_reformed_syllables():
    spec = from_dict({"language": "hy", "lexicon": {"Աստուած": "Աստ-ված"}})
    report = scan("Աստուած սեաւ\n", spec)
    assert report.lines[0].fit.count == 3
    assert [i.data["word"] for i in report.issues] == ["սեաւ"]  # the listed word is no note


@pytest.mark.parametrize("a", ["Իմ սարը՜", "Իմ սա՜րը"])
def test_an_exclamation_on_a_final_schwa_leaves_the_stress_on_the_vowel(a):
    assert hy_rhyme(a, "Իմ յարը") >= rhyme.THRESHOLD["perfect"]
    assert words(a)[1].sung(words(a)[1].readings[0].stress, mark=True) == "սա́-րը"


def test_no_stress_mark_ever_lands_on_a_schwa():
    (w,) = words("Ջանը՜մ")
    assert "ը́" not in w.sung(w.readings[0].stress, mark=True)


@pytest.mark.parametrize(
    "tag,name",
    [
        ("Կրկներգ՝ մեղմ", "Chorus: մեղմ"),
        ("Տուն 2՝ ռեփ", "Verse 2: Rap"),
        ("Կրկներգ։ բարձր", "Chorus: բարձր"),
        ("Պրիպև", "Chorus"),
        ("Քորուս", "Chorus"),
    ],
)
def test_armenian_section_separators_and_studio_words(tag, name):
    from ashugh import lyrics

    assert lyrics.suno_tag(tag) == name


def test_a_chorus_spec_reaches_a_chorus_tagged_with_an_armenian_separator():
    text = "[Կուպլետ 1]\nՍարերի վրա ամպեր են իջել,\n\n[Կրկներգ՝ մեղմ]\nԱրի, արի, իմ յար,\n"
    spec = from_dict({"language": "hy", "syllables": 10, "section": {"chorus": {"syllables": 6}}})
    report = scan(text, spec)
    assert not any("matches no section" in i.message for i in report.issues)
    assert report.lines[1].ok


def test_classical_spelling_is_named_once():
    report = scan("Կեանքս, իմ կեանքս\n", Spec(language="hy"))
    (note,) = [i for i in report.issues if "classical spelling" in i.message]
    assert (
        note.severity == "info" and note.message == "«Կեանքս» is classical spelling, read as Կյանքս"
    )


def test_reformed_spelling_gets_no_classical_note():
    report = scan("Կյանքս տվի քեզ\n", Spec(language="hy"))
    assert not any("classical" in i.message for i in report.issues)


def test_translate_from_latin_typed_armenian_with_its_source_lang_does_not_warn():
    from ashugh.proposers import StaticProposer
    from ashugh.translate import translate_song

    source = "Du im kyanqn es\nIm sirt@ qez e\n"
    result = translate_song(source, "ru", StaticProposer({}), rounds=1, source_lang="hy")
    assert not any("was read as" in w for w in result.warnings)


@pytest.mark.parametrize("line", ["XXI դար", "դար XXI"])
def test_a_tie_between_latin_and_armenian_words_is_armenian(line):
    report = scan(line + "\n")
    assert report.lines[0].line.lang == "hy"
    assert any("Roman numeral" in i.message for i in report.issues)


def test_a_tie_between_latin_and_english_words_stays_english():
    from ashugh.lang import detect

    assert detect(["love", "you"]) == "en"


def test_the_mcp_requests_schema_names_n():
    from ashugh.mcp import TOOLS

    assert TOOLS["requests"][1]["properties"]["n"]["type"] == "integer"


@pytest.mark.parametrize("line,shown", [("ՔԵԶ ՉԵՄ ՏԱ", "ՏԱ"), ("ՔՈ ՍԵՐԸ", "ՔՈ")])
def test_a_word_in_capitals_keeps_its_capitals(line, shown):
    ws = words(line)
    assert shown in {w.sung(w.readings[0].stress, mark=True) for w in ws}


@pytest.mark.parametrize(
    "latin,armenian",
    [
        ("@nkers u sirt@ het en", "ընկերս ու սիրտը հետ են"),
        ("əntaniqs u əspasum", "ընտանիքս ու ըսպասում"),
    ],
)
def test_latin_typed_schwas_read_as_the_armenian_letters(latin, armenian):
    lat, arm = analyze_lines(f"{latin}\n{armenian}", Spec(language="hy"))
    assert [w.size for w in lat.words] == [w.size for w in arm.words]
    assert all(w.lang == "hy" for w in lat.words)


def test_a_word_opening_with_a_latin_schwa_is_not_foreign():
    report = scan("əntaniqs u əspasum\n", Spec(language="hy"))
    assert not any("not Armenian" in i.message for i in report.issues)


def test_suno_writes_the_latin_schwa_once():
    from ashugh import suno

    out = suno.format_song(
        "@nkers u sirt@ het en\n", Spec(language="hy"), armenian="latin", tags=False
    )
    assert out.text.strip() == "ənkers u sirtə het en"


@pytest.mark.parametrize(
    "text,tokens",
    [
        ("write to john@mail.com", ["write", "to", "john", "mail", "com"]),
        ("sirt@5", ["sirt"]),
        ("me @ 5", ["me"]),
    ],
)
def test_an_at_sign_inside_an_address_is_no_letter(text, tokens):
    from ashugh.lyrics import tokenize

    assert tokenize(text) == tokens


def test_an_english_handle_is_read_as_its_name():
    (ln,) = analyze_lines("follow me @john tonight", Spec(language="en"))
    john = ln.words[2]
    assert john.text == "@john" and not john.guessed and john.size == 1


@pytest.mark.parametrize(
    "word,shown",
    [
        ("Բոնդ", "Բոնդ"), ("Հովարդ", "Հո-վարդ"), ("Էդմունդ", "Էդ-մունդ"), ("Ռոլանդ", "Ռո-լանդ"),
        ("Դիսնեյլենդ", "Դիս-նեյ-լենդ"), ("Մակդոնալդս", "Մակ-դո-նալդս"), ("ֆրենդ", "ֆը-րենդ"),
        ("Մակդոնալդ", "Մակ-դո-նալդ"),
    ],
)  # fmt: skip
def test_foreign_names_and_loans_take_no_possessive_schwa(word, shown):
    assert sung(word) == shown


@pytest.mark.parametrize(
    "word,shown",
    [
        ("հայերենդ", "հա-յե-րե-նըդ"), ("տունդ", "տու-նըդ"), ("անունդ", "ա-նու-նըդ"),
        ("բանդ", "բա-նըդ"), ("քայլդ", "քայ-լըդ"),
    ],
)  # fmt: skip
def test_a_native_word_still_takes_the_possessive(word, shown):
    assert sung(word) == shown


@pytest.mark.parametrize(
    "word,shown,phones",
    [
        ("Ինչ-որ", "Ինչ-որ", "intʃʰvoɾ"),
        ("Փարիզ-Երևան", "Փա-րիզ-Ե-րե-վան", "pʰaɾizjeɾevan"),
        ("Սայաթ-Նովա", "Սա-յաթ-Նո-վա", "sajatʰnova"),
    ],
)
def test_the_part_after_a_hyphen_opens_like_a_word(word, shown, phones):
    (w,) = words(word)
    assert w.sung() == shown
    assert "".join(w.readings[0].phones) == phones


@pytest.mark.parametrize(
    "mode,out",
    [("schwa", "Փարիզ-Երևան չըվերթով"), ("latin", "Pariz-Yerevan chəvertov")],
)
def test_suno_keeps_the_hyphen_of_a_compound(mode, out):
    from ashugh import suno

    text = suno.format_song("Փարիզ-Երևան չվերթով\n", Spec(language="hy"), armenian=mode, tags=False)
    assert text.text.strip() == out


def test_suno_latin_writes_the_v_of_inch_vor():
    from ashugh import suno

    text = suno.format_song(
        "Ինչ-որ մեկը կանչեց\n", Spec(language="hy"), armenian="latin", tags=False
    )
    assert text.text.startswith("Inch-vor ")


def test_a_capital_opening_a_hyphen_part_is_kept_in_syl():
    (w,) = words("Փարիզ-Երևան")
    assert w.sung(w.readings[0].stress, mark=True) == "Փա-րիզ-Ե-րե-վա́ն"
