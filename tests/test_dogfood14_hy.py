"""Round 14 of dogfooding, Armenian: what a songwriter found wrong."""

import pytest

from ashugh import suno
from ashugh.scan import analyze_lines
from ashugh.spec import Spec


def words(line: str):
    (ln,) = analyze_lines(line, Spec(language="hy"))
    return ln.words


@pytest.mark.parametrize(
    "line, k",
    [
        ("Ես ՔԵԶ եմ սիրում", 1),
        ("ՈՒՐ ես", 0),
        ("ԵՍ ու ԴՈՒ", 0),
        ("ԵՍ ու ԴՈՒ", 2),
        ("Դու ԻՄ սերն ես", 1),
        ("Ու ՆԱ եկավ", 1),
        ("ՄԵՐ երգը", 0),
        ("ՈՉ, ՉԷ", 0),
        ("ԻՆՁ տուր", 0),
    ],
)
def test_a_short_word_in_capitals_is_a_word(line, k):
    w = words(line)[k]
    assert not w.spelled and w.size == 1


@pytest.mark.parametrize(
    "token, size", [("ԱՄՆ", 3), ("ԵՊՀ", 3), ("ՀՀ", 2), ("ԱԺ", 2), ("ՀՀԿ-ն", 3)]
)
def test_abbreviations_are_still_spelt(token, size):
    (w,) = words(token)
    assert w.spelled and w.size == size


def test_suno_leaves_an_emphasized_word_as_written():
    out = suno.format_song("Ես ՔԵԶ եմ սիրում, ՈՒՐ ես, ԴՈՒ\n", tags=False).text
    assert out.startswith("Ես ՔԵԶ եմ սիրում, ՈՒՐ ես, ԴՈՒ")


def es_is_pronoun(line: str, nth: int = 0) -> bool:
    es = [w for w in words(line) if w.norm == "ես"][nth]
    return not es.clitic


@pytest.mark.parametrize(
    "line",
    [
        "Կերգեմ ես",
        "Սիրում եմ քեզ ես",
        "Չեմ մոռանա ես",
        "Մի օր ես կգայի",
        "Գիշերը ես չեկա",
        "Գիշերները ես քուն չեղա",
        "Քեզ համար միշտ կերգեմ ես,",
        "Հետո էլ ես գնացի",
    ],
)
def test_es_with_a_verb_of_i_in_its_clause_is_the_pronoun(line):
    assert es_is_pronoun(line)


@pytest.mark.parametrize(
    "line",
    [
        "Դու էլ ես գեղեցիկ",
        "Ե՞րբ ես գալու",
        "Ուր ես, ես կգամ",  # the first: the clause ends after it
        "Գիտեմ, որ դու ինձ սիրում ես",
        "Ինչու ես լռում",
        "Հայի պես ես խոսում",  # հայի is a genitive, no verb of I
    ],
)
def test_es_after_its_word_with_no_verb_of_i_is_the_auxiliary(line):
    assert not es_is_pronoun(line)


def test_suno_sings_the_pronoun_yes():
    out = suno.format_song("Կերգեմ ես\nԴու էլ ես գեղեցիկ\n", tags=False, armenian="latin").text
    assert "Kergem yes" in out and "Du el es" in out


def test_pick_rejects_a_candidate_with_digits():
    from ashugh.fit import fit_song
    from ashugh.proposers import StaticProposer
    from ashugh.spec import from_dict

    spec = from_dict({"language": "hy", "syllables": 7})
    res = fit_song(
        "[Տուն]\nԵս քեզ սիրում եմ շատ\n",
        spec,
        StaticProposer({2: ["Ես քեզ սիրում եմ 100 տարի"]}),
        rounds=1,
    )
    assert "100" not in res.text


def test_a_request_for_a_line_with_digits_says_to_spell_them_out():
    from ashugh.fit import requests_for
    from ashugh.spec import from_dict

    (req,) = requests_for(
        "[Տուն]\nԵս քեզ սիրում եմ 100 տարի\n", from_dict({"language": "hy", "syllables": 9})
    )
    assert any("digits" in p for p in req.problems)
    assert not any("syllables, slot" in p for p in req.problems)  # its count leaves them out


def syllable_range(line: str) -> tuple[int, int]:
    from ashugh import meter

    ws = words(line)
    return meter.syllable_range(ws, meter.fit(ws, "free"))


@pytest.mark.parametrize("line, fewest", [("Աղջիկն եկավ", 4), ("Արևն ելավ", 4), ("Աղջիկն իջավ", 4)])
def test_the_article_n_links_onto_a_word_in_e_as_onto_any_vowel(line, fewest):
    assert syllable_range(line)[0] == fewest


def test_an_iamb_line_with_a_linking_n_before_e_fits_eight():
    from ashugh.scan import scan
    from ashugh.spec import from_dict

    rep = scan(
        "Մեր ժողովուրդն ելավ կռվին\n",
        from_dict({"language": "hy", "syllables": 8, "meter": "iamb4"}),
    )
    assert rep.ok, [i.message for i in rep.issues if i.severity == "error"]


@pytest.mark.parametrize(
    "token, size", [("DM-ում", 3), ("VK-ում", 3), ("BTS-ի", 4), ("FB-ում", 3), ("KFC-ում", 4)]
)
def test_a_latin_abbreviation_with_an_armenian_ending_is_spelt(token, size):
    w = words(f"Ես դեռ քո {token} եմ")[3]
    assert w.size == size and w.lang == "hy"


def test_a_latin_word_with_an_ending_is_still_read_as_a_word():
    assert words("Տեսա TikTok-ում")[1].size == 3


@pytest.mark.parametrize(
    "line, mode, split, out",
    [
        ("Երևան, արևն ելավ, Սևան\n", "schwa", "none", "Երևան, արև"),
        ("Երևան, Սևան\n", "schwa", "none", "Սևան"),
        ("Երևանում արևը նաև ևս\n", "script", "all", "ևս"),
        ("Երևանում\n", "script", "all", "Ե-րե-վա-նում"),  # split at the hyphen: correct
        ("Եվրոպա\n", "schwa", "none", "Եվրոպա"),  # an եվ written as such stays
    ],
)
def test_suno_keeps_the_ligature_ev(line, mode, split, out):
    text = suno.format_song(line, tags=False, armenian=mode, split=split).text
    assert out in text and "Երեվան" not in text


SONG_WITH_LATIN = (
    "Ես քեզ սիրում եմ ամեն օր\nMtnem qo srtin, kyanqs, aynqan karotum em\nՈւ դու ինձ ես սիրում\n"
)


def test_a_latin_typed_line_in_an_armenian_song_is_armenian_without_lang():
    from ashugh.scan import scan

    rep = scan(SONG_WITH_LATIN)
    assert rep.lines[1].line.lang == "hy"
    assert rep.lines[1].fit.count == scan(SONG_WITH_LATIN, lang="hy").lines[1].fit.count


def test_an_english_line_in_an_armenian_song_stays_english():
    from ashugh.scan import scan

    rep = scan("Ես քեզ սիրում եմ ամեն օր\nI love you more than words can say\n")
    assert rep.lines[1].line.lang == "en"


LATIN_LINE = "Mtnem qo srtin u karotum\n"


def test_script_mode_keeps_a_latin_typed_line_as_written():
    out = suno.format_song(LATIN_LINE, tags=False, armenian="script", lang="hy").text
    assert out.startswith("Mtnem qo srtin u karotum")


def test_script_mode_still_splits_a_latin_typed_line():
    out = suno.format_song(LATIN_LINE, tags=False, armenian="script", split="all", lang="hy").text
    assert "ka-ro-tum" in out and "qo" in out


def test_schwa_mode_writes_a_latin_typed_line_as_latin_mode_does():
    schwa = suno.format_song(LATIN_LINE, tags=False, armenian="schwa", lang="hy").text
    latin = suno.format_song(LATIN_LINE, tags=False, armenian="latin", lang="hy").text
    assert schwa == latin


def test_the_armenian_hyphen_is_a_hyphen():
    (w,) = words("ԱՄՆ֊ից")
    assert w.spelled and w.size == 4


def test_presentation_ligatures_are_their_letters():
    plain = sum(w.size for w in words("ուրեմն մեր միակ"))
    assert sum(w.size for w in words("ուրեﬓ ﬔր ﬕակ")) == plain


@pytest.mark.parametrize("word, value", [("Երևան", "Ե-րե-վան"), ("արևմուտք", "ա-րեվ-մուտք")])
def test_the_lexicon_takes_the_tools_own_split_of_ev(word, value):
    from ashugh.lang import hy

    assert hy.override_error(word, value) is None


@pytest.mark.parametrize("tag, out", [("[Նվագ]", "[Instrumental]"), ("[Մեներգ]", "[Solo]")])
def test_more_armenian_tags(tag, out):
    from ashugh import lyrics

    assert lyrics.retag(tag) == out


def test_a_held_note_stays_long_in_latin():
    out = suno.format_song("Օօօ, քնիր\n", tags=False, armenian="latin").text
    assert out.startswith("Ooo,")


@pytest.mark.parametrize("line, lang", [("XXI դարում ենք", "hy"), ("Тигран II и Пётр I", "ru")])
def test_a_roman_numeral_is_warned_about(line, lang):
    from ashugh.scan import scan
    from ashugh.spec import Spec as S

    rep = scan(line + "\n", S(language=lang))
    assert any("Roman numeral" in i.message for i in rep.issues)


@pytest.mark.parametrize("line", ["I love you", "We MIX it up"])
def test_english_capitals_are_no_roman_numerals(line):
    from ashugh.scan import scan
    from ashugh.spec import Spec as S

    rep = scan(line + "\n", S(language="en"))
    assert not any("Roman numeral" in i.message for i in rep.issues)
