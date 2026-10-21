"""Round 17 of dogfooding, Armenian: what a songwriter found wrong."""

import pytest

from ashugh import lyrics, meter, rhyme
from ashugh.scan import analyze_lines, scan
from ashugh.spec import Spec, from_dict


def words(line: str, lang: str = "hy"):
    (ln,) = analyze_lines(line, Spec(language=lang))
    return ln.words


def langs(line: str, lang: str = "hy") -> list[str]:
    return [w.lang for w in words(line, lang)]


def hy_rhyme(a: str, b: str) -> float:
    lines = analyze_lines(f"{a}\n{b}", Spec(language="hy"))
    return rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))[0]


@pytest.mark.parametrize("line", ["Վերջ։", "Տուն։", "Վերջ:", "Տուն:", "End:"])
def test_a_one_word_sung_line_is_no_section_label(line):
    assert lyrics.plain_label(line) is None and not lyrics.is_tag(line)


@pytest.mark.parametrize(
    "line,tag",
    [
        ("Կրկներգ:", "[Կրկներգ]"),
        ("Տուն 2:", "[Տուն 2]"),
        ("Chorus:", "[Chorus]"),
        ("Bridge", "[Bridge]"),
    ],
)
def test_a_section_label_still_is_one(line, tag):
    assert lyrics.plain_label(line) == tag


def test_a_sung_verj_is_counted_and_kept_by_suno():
    from ashugh import suno

    text = "Արի ինձ մոտ, իմ յար,\nՎերջ։\n"
    report = scan(text, Spec(language="hy"))
    assert [lr.line.text for lr in report.lines] == ["Արի ինձ մոտ, իմ յար,", "Վերջ։"]
    out = suno.format_song(text, Spec(language="hy"), tags=False).text
    assert "Վերջ։" in out and "[End]" not in out


@pytest.mark.parametrize(
    "line,english",
    [
        ("Դու ինձ տանում ես higher", ["higher"]),
        ("Մենք պարում ենք laughing all night", ["laughing", "all", "night"]),
        ("Ես ու դու միասին ենք on the highway", ["on", "the", "highway"]),
        ("Իմ սիրտը քեզ մոտ է my neighbors know", ["my", "neighbors", "know"]),
    ],
)
def test_english_words_in_an_armenian_line_stay_english(line, english):
    ws = words(line)
    assert [w.text for w in ws if w.lang == "en"] == english


@pytest.mark.parametrize(
    "line,english",
    [
        ("Du sexy es, kez em sirum", ["sexy"]),
        ("Kez em spasum, next time mi gna", ["next", "time"]),
        ("Kyanqs party a, kez em sirum", ["party"]),
    ],
)
def test_a_latin_typed_line_borrows_pop_english(line, english):
    assert [w.text for w in words(line) if w.lang == "en"] == english


def test_an_english_line_with_gh_words_under_an_armenian_spec_is_english():
    assert set(langs("She laughs and sighs tonight")) == {"en"}
    assert sum(w.size for w in words("She laughs and sighs tonight")) == 6


@pytest.mark.parametrize(
    "line,count",
    [
        ("Ari, ari, mi gna", 7),
        ("Ari, ari, im bari jan", 8),
        ("Du im srtis mej es, my love", 8),
        ("Ari, ari, im anush yar", 8),
    ],
)
def test_latin_typed_armenian_that_looks_english_is_armenian(line, count):
    ws = words(line)
    assert sum(w.size for w in ws) == count
    assert all(w.lang == "hy" for w in ws if w.norm not in ("my", "love"))


def test_a_latin_typed_word_rhymes_with_its_armenian_spelling():
    assert hy_rhyme("ari", "բարի") >= rhyme.THRESHOLD["perfect"]


@pytest.mark.parametrize(
    "line", ["I love you baby", "Midnight city lights", "Dance with me tonight", "I need an inch"]
)
def test_english_lines_in_an_armenian_song_stay_english(line):
    assert set(langs(line)) == {"en"}


def test_burns_is_still_english():
    from ashugh.lang import latin_armenian

    for line in [
        "Thou need na start awa sae hasty,",
        "Wi' bickering brattle!",
        "Wee, sleekit, cow'rin, tim'rous beastie,",
    ]:
        assert not latin_armenian(lyrics.tokenize(line))


def test_a_latin_typed_candidate_is_accepted_for_a_latin_typed_song():
    from ashugh.fit import fit_song
    from ashugh.proposers import StaticProposer

    text = "Ari, ari, im anush yar,\nQez em spasum gisherov,\n"
    spec = from_dict({"language": "hy", "syllables": 8})
    result = fit_song(text, spec, StaticProposer({2: ["Ari, ari, im bari jan,"]}), rounds=1)
    rejected = [r["why"] for u in result.unresolved for r in u.rejected]
    assert not any("not in Armenian" in why for why in rejected)


def sung(word: str) -> str:
    return words(word)[0].sung()


@pytest.mark.parametrize(
    "word,shown",
    [
        ("բոյդ", "բոյդ"), ("շոյված", "շոյ-ված"), ("բոյկոտ", "բոյ-կոտ"), ("Դետրոյտ", "Դետ-րոյտ"),
        ("Ջոյս", "Ջոյս"), ("հռոմեացի", "հը-ռո-մե-ա-ցի"),
    ],
)  # fmt: skip
def test_a_modern_word_with_oy_or_eats_is_not_classical(word, shown):
    w = words(word)[0]
    assert w.sung() == shown and not any("classical" in n for n in w.notes)


@pytest.mark.parametrize(
    "word,shown",
    [
        ("յոյս", "հույս"), ("լոյսը", "լույ-սը"), ("քոյր", "քույր"), ("Իւր", "Իր"), ("իւղ", "յուղ"),
        ("իւրաքանչիւր", "յու-րա-քան-չյուր"), ("եօթը", "յո-թը"), ("տեսայ", "տե-սա"),
        ("հայեացք", "հա-յացք"),
    ],
)  # fmt: skip
def test_classical_spelling_is_read_as_the_reform_spells_it(word, shown):
    assert sung(word) == shown


def test_classical_aorist_rhymes_with_vra():
    assert hy_rhyme("Ես քեզ տեսայ", "Սարի վրայ") >= rhyme.THRESHOLD["near"]  # սա / րա


@pytest.mark.parametrize(
    "word,shown",
    [("բոլորդ", "բո-լո-րըդ"), ("ձորդ", "ձո-րըդ"), ("աղբյուրդ", "աղ-բյու-րըդ")],
)
def test_a_word_in_or_or_ur_takes_the_possessive(word, shown):
    assert sung(word) == shown


@pytest.mark.parametrize("word", ["վարորդ", "գնորդ", "երկրորդ", "ժողովուրդ", "խորդ", "առաջնորդ"])
def test_a_stem_in_ord_or_urd_keeps_it(word):
    assert "ըդ" not in sung(word)


def test_an_english_i_in_an_armenian_line_is_no_numeral():
    report = scan("Ես քեզ սիրում եմ, I love you\n", Spec(language="hy"))
    assert not any("Roman" in i.message for i in report.issues)
    report = scan("Եկավ XXI դարը\n", Spec(language="hy"))
    assert any("Roman" in i.message for i in report.issues)


@pytest.mark.parametrize(
    "text",
    [
        "Արի ինձ մոտ, իմ յար x2\nՄնա ինձ հետ, իմ ցավ\n",
        "Hold me tonight x2\nI'm feeling cold\n",
        "Hold me tonight (x2)\nI'm feeling cold\n",
    ],
)
def test_a_line_with_a_repeat_mark_keeps_its_rhyme(text):
    report = scan(text, from_dict({"rhyme": "AA"}))
    assert any(i.code == "rhyme" and i.severity == "error" for i in report.issues)


def test_a_year_in_digits_still_leaves_the_rhyme():
    report = scan("I was born in '99\nAnd still I shine\n", from_dict({"rhyme": "AA"}))
    assert not any(i.code == "rhyme" and i.severity == "error" for i in report.issues)


def test_suno_writes_a_repeated_line_out():
    from ashugh import suno

    out = suno.format_song("Hold me tonight x2\nArmy of 2\n", tags=False)
    assert out.text == "Hold me tonight\nHold me tonight\nArmy of 2\n"
    assert any(n.kind == "repeat" for n in out.notes)


@pytest.mark.parametrize(
    "tag,name,key",
    [
        ("Կրկներգ 2 անգամ", "Chorus x2", "chorus"), ("Припев 2 раза", "Chorus x2", "chorus"),
        ("Chorus 3 times", "Chorus x3", "chorus"), ("Կրկնել կրկներգը", "Chorus", "chorus"),
        ("Повтор припева", "Chorus", "chorus"),
    ],
)  # fmt: skip
def test_repeat_words_in_a_tag(tag, name, key):
    assert lyrics.suno_tag(tag) == name and lyrics.section_key(tag) == key


@pytest.mark.parametrize(
    "line,out",
    [
        ("[Կրկներգ] x2\n", "[Chorus x2]\n"), ("[Chorus] x2\n", "[Chorus x2]\n"),
        ("Припев (х2)\n", "[Chorus x2]\n"), ("Chorus (2x)\n", "[Chorus 2x]\n"),
        ("Повтор припева\n", "[Chorus]\n"),
    ],
)  # fmt: skip
def test_a_repeat_mark_by_a_tag_goes_inside_it(line, out):
    assert lyrics.is_tag(line) and lyrics.retag(line) == out


def test_a_chorus_spec_reaches_a_chorus_twice():
    text = "[Կրկներգ 2 անգամ]\nԱրի, արի, իմ յար,\nԱրի, արի, ջան\n"
    spec = from_dict({"language": "hy", "section": {"chorus": {"syllables": 6}}})
    report = scan(text, spec)
    assert not report.lines[1].ok and not any(
        "matches no section" in i.message for i in report.issues
    )


def test_ev_typed_as_two_letters_opens_a_clause():
    a, b = words("Դու եւ ես"), words("Դու և ես")
    assert [w.stress_options() for w in a] == [w.stress_options() for w in b]


@pytest.mark.parametrize(
    "tag,out",
    [
        ("[Կրկներգ - Արական ձայն]", "[Chorus - Male Vocal]"),
        ("[Припев - мужской вокал]", "[Chorus - Male Vocal]"),
    ],
)
def test_a_voice_name_in_a_tag_note_is_translated(tag, out):
    assert lyrics.retag(tag) == out


def test_a_passing_line_asked_for_its_partners_refrain_is_told_why():
    from ashugh.fit import requests_for

    text = (
        "[Chorus]\nԱրի ինձ մոտ, իմ յար,\nՄնա ինձ հետ մինչև լույս,\n"
        "Արի ինձ մոտ, իմ յար,\nԴու ես իմ միակ հույսը լույս։\n"
    )
    spec = from_dict({"language": "hy", "syllables": [6, 7, 6, 8], "rhyme": "ABAB"})
    reqs = requests_for(text, spec)
    assert reqs and all(r.problems for r in reqs)


HOOK = (
    "[Chorus]\nԱրի ինձ մոտ, յար,\nՄնա ինձ հետ մինչև լույս,\n"
    "Արի ինձ մոտ, յար,\nԻմ միակ ու վերջին հույս։\n"
)


def test_a_hook_repeated_in_its_own_rhyme_group_is_repaired_alike():
    from ashugh.fit import fit_song
    from ashugh.proposers import StaticProposer

    spec = from_dict({"language": "hy", "syllables": [6, 7, 6, 7], "rhyme": "ABAB"})
    cands = StaticProposer({2: ["Արի ինձ մոտ, իմ յար,", "Արի, արի, իմ յար,"]})
    result = fit_song(HOOK, spec, cands, rounds=1)
    new = {c.line: c.new for c in result.changes}
    assert new[2] == new[4] and not result.unresolved


def test_a_translated_hook_is_translated_both_times():
    from ashugh.proposers import StaticProposer
    from ashugh.translate import translate_song

    source = (
        "Take me home, take me home,\nWhere the river flows,\n"
        "Take me home, take me home,\nWhere the poppy grows.\n"
    )
    cands = StaticProposer({1: ["Տար ինձ տուն, տար ինձ տուն,"]})
    result = translate_song(source, "hy", cands, rounds=1)
    new = {c.line: c.new for c in result.changes}
    assert new.get(1) == new.get(3) == "Տար ինձ տուն, տար ինձ տուն,"


def test_two_different_lines_on_one_rhyme_word_are_still_no_rhyme():
    from ashugh.fit import fit_song
    from ashugh.proposers import StaticProposer

    text = "Արի ինձ մոտ, ջան,\nՄնա ինձ հետ, լույս,\nԵս քեզ կսպասեմ,\nԴու իմ հույսն ես, հույս,\n"
    spec = from_dict({"language": "hy", "rhyme": "ABAB"})
    result = fit_song(text, spec, StaticProposer({3: ["Ես քեզ կսպասեմ ջան,"]}), rounds=1)
    assert not any(c.line == 3 for c in result.changes)


def test_an_ending_rule_takes_the_optional_schwa_that_gives_it():
    report = scan("Իմ կյանքը քո սերն\n", from_dict({"language": "hy", "endings": "f"}))
    assert report.lines[0].ok and report.lines[0].fit.count == 6
    report = scan("Իմ կյանքը քո սերն\n", from_dict({"language": "hy", "endings": "m"}))
    assert report.lines[0].ok and report.lines[0].fit.count == 5


@pytest.mark.parametrize(
    "key,value", [("srtis", "sər-tis"), ("srtis", "սըր-տիս"), ("սրտիս", "սըր-տիս")]
)
def test_a_lexicon_entry_reaches_a_latin_typed_word(key, value):
    spec = from_dict({"language": "hy", "lexicon": {key: value}})
    (ln,) = analyze_lines("Du im srtis mej es", spec)
    (w,) = [w for w in ln.words if w.text == "srtis"]
    assert w.size == 2 and w.readings[0].source == "user"


def test_an_english_lexicon_entry_still_takes_arpabet():
    spec = from_dict({"lexicon": {"gonna": "G AA1 N AH0"}})
    assert spec.lexicon["gonna"] == "G AA1 N AH0"


@pytest.mark.parametrize("word", ["Մմմ", "մմ", "Շշշ", "Տսսս", "Ննն"])
def test_a_hum_is_one_held_sound_with_no_schwa(word):
    (w,) = words(word)
    assert w.size == 1 and w.held and "ը" not in w.sung()


def test_suno_writes_a_hum_as_it_is():
    from ashugh import suno

    for mode, out in (("schwa", "Մմմ, իմ յար"), ("latin", "Mmm, im yar")):
        text = suno.format_song(
            "Մմմ, իմ յար\n", Spec(language="hy"), armenian=mode, tags=False
        ).text
        assert text.strip() == out


def test_chat_eight_for_u_is_named():
    report = scan("Inch8 es lr8m, jan?\n", Spec(language="hy"))
    (issue,) = [i for i in report.issues if i.code == "script"]
    assert issue.message == "8 typed for ու is not read" and "Inch8, lr8m" in issue.detail


def test_an_english_number_word_with_8_is_no_eight_for_u():
    report = scan("Call me at 8\n", Spec(language="en"))
    assert not any("ու" in i.message for i in report.issues)


@pytest.mark.parametrize(
    "line", ["Տղա: Արի ինձ մոտ, իմ յար", "Աղջիկ: Չեմ գա", "ԱՐՄԵՆ: Արի", "Она: Я жду"]
)
def test_an_armenian_or_russian_singer_label_is_warned(line):
    assert any(i.message == "a label for who sings is sung" for i in scan(line + "\n").issues)


def test_a_latin_typed_song_asks_and_keeps_latin_letters():
    from ashugh.fit import fit_song, requests_for
    from ashugh.proposers import StaticProposer

    text = "Qez em spasum gisherov,\nSrtis mej ches, chem karoghanum,\n"
    spec = from_dict({"language": "hy", "syllables": 7})
    (req, *_) = requests_for(text, spec)
    assert req.script == "latin"
    result = fit_song(text, spec, StaticProposer({1: ["Քեզ եմ սպասում հիմա,"]}), rounds=1)
    whys = [r["why"] for u in result.unresolved for r in u.rejected]
    assert "Armenian in the wrong letters: the song writes it in Latin letters" in whys
