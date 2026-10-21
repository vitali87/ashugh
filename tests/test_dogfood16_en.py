"""Round 16 of dogfooding, English: what a songwriter found wrong."""

import pytest

from ashugh import meter, rhyme
from ashugh.scan import analyze_lines, scan
from ashugh.spec import Spec, from_dict


def words(line: str, lang: str = "en"):
    (ln,) = analyze_lines(line, Spec(language=lang))
    return ln.words


def sizes(word: str) -> set[int]:
    w = words(word)[0]
    return {len(rhyme.nuclei(r.phones)) for r in w.readings}


def en_rhyme(a: str, b: str) -> float:
    lines = analyze_lines(f"{a}\n{b}", Spec(language="en"))
    return rhyme.match(*(rhyme.tails(ln, meter.fit(ln.words, "free")) for ln in lines))[0]


def check(text: str, **spec):
    return scan(text, from_dict({"language": "en", **spec}))


@pytest.mark.parametrize(
    "word,n",
    [
        ("ev'ry", 2), ("ev'rything", 3), ("ev'ning", 2), ("sov'reign", 2), ("prob'ly", 2),
        ("fam'ly", 2), ("hist'ry", 2), ("diff'rent", 2), ("fav'rite", 2), ("gen'ral", 2),
        ("vict'ry", 2), ("cam'ra", 2), ("ev'ryone", 3), ("ev'rywhere", 3), ("choc'late", 2),
        ("bus'ness", 2), ("cath'lic", 2), ("temp'rance", 2), ("ling'ring", 2),
        ("list'ning", 2), ("sweet'ning", 2), ("pow'r", 1), ("heav'n", 1), ("wand'ring", 2),
        ("mem'ry", 2), ("flow'r", 1),
    ],
)  # fmt: skip
def test_an_apostrophe_leaves_out_one_vowel_of_the_full_word(word, n):
    assert sizes(word) == {n}


def test_a_hymn_line_with_evry_is_its_eight_syllables():
    assert not check("In ev'ry heart and ev'ry home\n", syllables=6).lines[0].ok
    assert check("In ev'ry heart and ev'ry home\n", syllables=8).lines[0].ok


@pytest.mark.parametrize(
    "word,shown",
    [("ev'ryone", "ev-ry-one"), ("ev'rywhere", "ev-ry-where"), ("whate'er", "what-e'er")],
)
def test_an_elided_word_is_shown_in_its_parts(word, shown):
    assert words(word)[0].sung() == shown


@pytest.mark.parametrize("word", ["whate'er", "where'er", "howe'er", "whene'er"])
def test_eer_is_ever_without_its_v(word):
    assert sizes(word) == {2}


def test_whateer_rhymes_with_there():
    assert en_rhyme("whate'er", "there") >= rhyme.THRESHOLD["perfect"]


@pytest.mark.parametrize("word", ["e'er", "ne'er", "o'er", "e'en"])
def test_a_one_syllable_elision_stays_one(word):
    assert sizes(word) == {1}


def test_thee_leans_on_its_verb():
    text = "O Lord, we come to praise thee\nWith all our voice we raise thee\n"
    report = check(text, meter="iamb", feet=3, rhyme="AA")
    assert all(lr.ok for lr in report.lines), [i.message for i in report.issues]


def test_two_verbs_before_thee_do_not_rhyme():
    assert en_rhyme("praise thee", "love thee") < rhyme.THRESHOLD["near"]
    text = "O Lord, we come to praise thee\nWith all our hearts we love thee\n"
    assert any(i.code == "rhyme" for i in check(text, rhyme="AA").issues)


@pytest.mark.parametrize(
    "text",
    [
        "I humbly bow before you\nForever I adore you\n",
        "There's nothing left between us\nNo light from distant Venus\n",
    ],
)
def test_a_pronoun_leans_on_a_two_syllable_preposition(text):
    report = check(text, meter="iamb", feet=3, rhyme="AA")
    assert all(lr.ok for lr in report.lines), [i.message for i in report.issues]


def test_under_me_rhymes_with_thunder_me():
    text = "The storm clouds gather, thunder me\nThe ground is breaking under me\n"
    assert all(lr.ok for lr in check(text, rhyme="AA").lines)


@pytest.mark.parametrize(
    "text",
    [
        "You play me like a broken record\nThe only song that I adored\n",
        "Put on the old record\nThe crowd adored\n",
        "We cross the burning desert\nForever alert\n",
        "I gave my sweetest present\nTo you who still resent\n",
        "I hear the howling wind\nAnd you were never kind\n",
    ],
)
def test_a_noun_stays_a_noun_past_its_adjective(text):
    assert any(i.code == "rhyme" for i in check(text, rhyme="AA").issues)


@pytest.mark.parametrize(
    "text",
    [
        "I hear the howling wind\nAnd now I've sinned\n",
        "We will record\nThe songs we adored\n",
        "I want to present\nThe gift that I meant\n",
    ],
)
def test_the_reading_its_context_allows_still_rhymes(text):
    assert not any(i.code == "rhyme" for i in check(text, rhyme="AA").issues)


def test_burns_is_english():
    text = (
        "Wee, sleekit, cow'rin, tim'rous beastie,\nO, what a panic's in thy breastie!\n"
        "Thou need na start awa sae hasty,\nWi' bickering brattle!\n"
        "I wad be laith to rin an' chase thee,\nWi' murd'ring pattle!\n"
    )
    report = scan(text)
    assert all(lr.line.lang == "en" for lr in report.lines)


@pytest.mark.parametrize(
    "line",
    [
        "Ari ari im anush yar",
        "Kez em sirum du im kyanqn es",
        "Du im kyanqn es",
        "Ari mot, yars, chem karogh aranc qez aprel",
        "T'agavor u ch'em gnum",
    ],
)
def test_latin_typed_armenian_is_still_found(line):
    from ashugh.lang import latin_armenian
    from ashugh.lyrics import tokenize

    assert latin_armenian(tokenize(line))


@pytest.mark.parametrize(
    "word,shown",
    [
        ("loveliest", "love-li-est"), ("loneliest", "lone-li-est"), ("lonelier", "lone-li-er"),
        ("stateliest", "state-li-est"), ("lovelier", "love-li-er"),
    ],
)  # fmt: skip
def test_ier_and_iest_are_built_on_the_y_adjective(word, shown):
    w = words(word)[0]
    assert w.sung() == shown and not w.guessed and w.readings[0].stress == 0


def test_the_loneliest_night_is_eight_syllables():
    assert check("The loneliest night of the year\n", syllables=8).lines[0].ok


@pytest.mark.parametrize(
    "word,vowel",
    [
        ("hopeth", "oʊ"), ("shineth", "aɪ"), ("careth", "ɛ"), ("hideth", "aɪ"),
        ("rideth", "aɪ"), ("hidest", "aɪ"), ("ripest", "aɪ"), ("abideth", "aɪ"),
    ],
)  # fmt: skip
def test_eth_and_est_keep_a_silent_e_stems_vowel(word, vowel):
    w = words(word)[0]
    r = w.readings[0]
    assert r.phones[rhyme.nuclei(r.phones)[r.stress]] == vowel


@pytest.mark.parametrize(
    "word,shown", [("calleth", "cal-leth"), ("knowest", "know-est"), ("openeth", "o-pen-eth")]
)
def test_a_stem_with_no_silent_e_stays(word, shown):
    assert words(word)[0].sung() == shown


def test_bakers_hymn_scans_and_rhymes():
    text = "Lord, thy word abideth\nAnd our footsteps guideth\n"
    report = check(text, meter="trochee", feet=3, rhyme="AA")
    assert all(lr.ok for lr in report.lines), [i.message for i in report.issues]


@pytest.mark.parametrize("word", ["our", "ours"])
def test_our_is_one_syllable(word):
    assert sizes(word) == {1}


def test_a_line_opening_on_our_is_an_iamb():
    report = scan("Our love will never die\nOur hearts will always fly\n")
    assert report.units[0].meter == "iamb" and report.lines[0].fit.count == 6
    assert not [i for i in report.issues if "our" in i.message.lower()]


@pytest.mark.parametrize("a,b", [("our", "power"), ("ours", "flowers")])
def test_our_still_rhymes_with_power(a, b):
    assert en_rhyme(a, b) >= rhyme.THRESHOLD["perfect"]


def test_miles_is_one_syllable_at_a_line_end():
    report = scan("I walked a thousand miles\nTo see your lovely smiles\n")
    assert [lr.fit.count for lr in report.lines] == [6, 6]
    assert (
        check("We think na on the lang Scots miles\n", meter="iamb", feet=4).lines[0].fit.count == 8
    )


def test_a_word_listed_short_first_may_still_be_sung_long():
    w = words("miles")[0]
    assert w.drop is not None and w.size == 2 and w.drop_cost < 0  # mi-les if the line asks


@pytest.mark.parametrize(
    "line,word,stress",
    [
        ("I still recall every wondrous meeting", "recall", 1),
        ("We gladly record the show", "record", 1),
        ("I always present my case", "present", 1),
    ],
)
def test_a_subject_past_an_adverb_makes_a_verb(line, word, stress):
    w = next(w for w in words(line) if w.norm == word)
    assert {r.stress for r in w.readings} == {stress}


LABELLED = (
    "Chorus:\nOh, take me home tonight\nAnd hold me till the light\n\n"
    "Verse 1:\nI walked along the road\n\nRepeat Chorus\n\nCHORUS x2\n"
)


@pytest.mark.parametrize(
    "line,tag",
    [
        ("Chorus:", "[Chorus]"), ("Verse 1:", "[Verse 1]"), ("CHORUS x2", "[CHORUS x2]"),
        ("Repeat Chorus", "[Chorus]"), ("Bridge", "[Bridge]"), ("Припев:", "[Припев]"),
        ("Կրկներգ՝", "[Կրկներգ]"), ("Hook:", "[Hook]"),
    ],
)  # fmt: skip
def test_a_plain_text_section_label_is_a_tag(line, tag):
    from ashugh import lyrics

    assert lyrics.plain_label(line) == tag and lyrics.is_tag(line)


@pytest.mark.parametrize("line", ["Վերջ", "Տուն", "The End", "Hook", "Love me", "Chorus girl"])
def test_a_lyric_that_only_looks_like_a_label_is_sung(line):
    from ashugh import lyrics

    assert lyrics.plain_label(line) is None


def test_labels_are_not_counted_and_name_their_sections():
    report = scan(LABELLED)
    assert [lr.line.number for lr in report.lines] == [2, 3, 6]
    assert [lr.line.section for lr in report.lines] == ["Chorus", "Chorus", "Verse 1"]
    assert not report.issues


def test_suno_turns_labels_into_tags():
    from ashugh import suno

    out = suno.format_song(LABELLED).text
    assert out.splitlines()[0] == "[Chorus]" and "[Verse 1]" in out and "Chorus:" not in out
    assert "Repeat Chorus" not in out and "[Chorus x2]" in out


@pytest.mark.parametrize(
    "line,name",
    [
        ("FREDERIC: Oh, is there not one maiden breast", "FREDERIC"),
        ("MABEL: Poor wand'ring one!", "MABEL"),
        ("Call: who will come with me", "Call"),
    ],
)
def test_a_label_for_who_sings_is_warned(line, name):
    report = scan(line + "\n")
    (issue,) = [i for i in report.issues if i.message == "a label for who sings is sung"]
    assert f"«{name}:»" in issue.detail


@pytest.mark.parametrize("line", ["OK: let it go", "I said: come home", "Time: it flies"])
def test_a_colon_after_a_word_is_no_label(line):
    assert not any("who sings" in i.message for i in scan(line + "\n").issues)


@pytest.mark.parametrize(
    "text,meter_name",
    [
        (
            "Don't let go, don't let go of the night\n"
            "Don't you know, don't you know it's alright\n",
            "anapest",
        ),
        ("Stay, oh stay till the morning\n", "dactyl"),
        (
            "Once in this ballroom the lovers were turning,\n"
            "Round as the moon while the music would flow,\n",
            "dactyl",
        ),
        ("The harbor lights are burning low\nAnd all the boats are coming home\n", "iamb"),
        ("Tiger, tiger, burning bright\nIn the forests of the night\n", "trochee"),
    ],
)
def test_monosyllables_are_set_by_their_weight(text, meter_name):
    assert scan(text).units[0].meter == meter_name


def test_an_anapest_spec_is_derived_from_monosyllabic_anapests():
    from ashugh.translate import derive_spec

    text = "Don't let go, don't let go of the night\nDon't you know, don't you know it's alright\n"
    data = derive_spec(scan(text), {"syllables", "meter"})["stanza"]["1"]
    assert data["meter"] == "anapest" and data["feet"] == [3, 3]


@pytest.mark.parametrize("a", ["L.A.", "U.S.A.", "a.k.a."])
def test_a_dotted_abbreviation_ends_on_its_letter(a):
    assert en_rhyme(a, "day") >= rhyme.THRESHOLD["perfect"]


def test_born_in_the_usa_rhymes_with_today():
    text = "I was born down in the U.S.A.\nAnd I'm living here today\n"
    assert all(lr.ok for lr in check(text, rhyme="AA").lines)


def test_a_lone_a_is_still_the_article():
    (a,) = [w for w in words("I want a song") if w.norm == "a"]
    assert a.clitic


def test_a_rhyme_on_a_promoted_last_syllable_ends_masculine():
    from ashugh.translate import derive_spec

    text = "Every night I am chasing a melody\nAnd the music is setting me free\n"
    data = derive_spec(scan(text), {"rhyme", "endings"})
    assert data["stanza"]["1"]["endings"] == "mm"


@pytest.mark.parametrize(
    "a,b",
    [("without you", "about you"), ("under me", "thunder me"), ("before you", "adore you")],
)
def test_a_pronoun_leans_on_a_long_preposition_in_a_short_query(a, b):
    assert en_rhyme(a, b) >= rhyme.THRESHOLD["perfect"]


def test_a_pronoun_after_a_short_preposition_alone_is_stressed():
    assert en_rhyme("to me", "free") >= rhyme.THRESHOLD["perfect"]


def test_over_and_lover_are_still_no_rhyme():
    assert en_rhyme("over you", "lover, you") < rhyme.THRESHOLD["near"]


@pytest.mark.parametrize(
    "line,out",
    [
        ("She startled and tangled", "She star-tled and tan-gled"),
        ("He whistled and dazzled", "He whis-tled and daz-zled"),
        ("The candles and the bottles", "The can-dles and the bot-tles"),
        ("At James's and Charles's", "At James-'s and Charles-'s"),
        ("The hurricane's eye", "The hur-ri-cane's eye"),
        ("He learnèd much", "He learn-èd much"),
    ],
)
def test_suno_splits_le_endings_and_possessives_where_they_are_sung(line, out):
    from ashugh import suno

    got = suno.format_song(line + "\n", Spec(language="en"), split="all", tags=False).text
    assert got.strip() == out


@pytest.mark.parametrize(
    "word", ["willow", "pillow", "studio", "video", "radio", "scenario", "shadow", "window"]
)
def test_a_final_o_rhymes_the_same_whatever_cmudict_marks(word):
    assert en_rhyme(word, "go") >= rhyme.THRESHOLD["perfect"]


def test_a_final_reduced_vowel_is_still_no_rhyme():
    assert en_rhyme("sofa", "day") < rhyme.THRESHOLD["near"]


@pytest.mark.parametrize(
    "line,numeral",
    [
        ("My grandpa fought in World War II", "II"),
        ("Henry VIII was king", "VIII"),
        ("Louis XIV danced", "XIV"),
    ],
)
def test_a_roman_numeral_in_english_is_warned(line, numeral):
    (issue,) = [i for i in scan(line + "\n").issues if "Roman numeral" in i.message]
    assert issue.detail.startswith(numeral)


@pytest.mark.parametrize("line", ["I saw a CD", "I mix it up", "I am here", "Mix it, DJ"])
def test_a_word_or_pronoun_is_no_roman_numeral(line):
    assert not any("Roman numeral" in i.message for i in scan(line + "\n").issues)


@pytest.mark.parametrize(
    "text",
    ["Oh please don't tear\nThe ones I hold so dear\n", "Please lead\nThe way to bed\n"],
)
def test_a_verb_heteronym_rhymes_by_its_verb_vowel(text):
    assert any(i.code == "rhyme" for i in check(text, rhyme="AA").issues)


@pytest.mark.parametrize(
    "text",
    [
        "I shed a tear\nFor you my dear\n",
        "Don't tear\nMy coat, I swear\n",
        "I wound the clock\nAnd turned the lock\n",
        "Please lead\nThe way, indeed\n",
    ],
)
def test_the_vowel_the_context_allows_still_rhymes(text):
    assert not any(i.code == "rhyme" for i in check(text, rhyme="AA").issues)


def test_leant_is_one_syllable():
    report = check("I leant upon a coppice gate\n", meter="iamb", feet=4)
    assert report.lines[0].fit.count == 8 and report.lines[0].ok


def test_a_tag_after_a_blank_line_opens_its_own_section():
    text = (
        "[Verse 1]\nI walked along the empty street\n\n[Instrumental]\n\n"
        "[Spoken Word]\nAnd then she said, I'll never come back here again\n"
    )
    spec = from_dict(
        {"language": "en", "syllables": 8, "section": {"spoken word": {"syllables": 12}}}
    )
    report = scan(text, spec)
    assert report.lines[1].line.section == "Spoken Word" and all(lr.ok for lr in report.lines)


def test_a_style_tag_right_under_a_section_still_belongs_to_it():
    report = scan("[Chorus]\n[Female Vocal]\nOh take me home tonight\n")
    assert report.lines[0].line.section == "Chorus"


@pytest.mark.parametrize("word", ["blesséd", "wingéd", "blessèd", "wingèd"])
def test_an_accented_ed_is_sung(word):
    assert sizes(word) == {2}


@pytest.mark.parametrize(
    "text,count", [("Go\n", "**1 syllable**"), ("Go home\n", "**2 syllables**")]
)
def test_the_hover_counts_in_the_singular_for_one(tmp_path, text, count):
    from ashugh.lsp import Server

    uri = (tmp_path / "s.txt").as_uri()
    server = Server()
    doc = {"textDocument": {"uri": uri, "languageId": "lyrics", "version": 1, "text": text}}
    server.handle({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": doc})
    hover = {"textDocument": {"uri": uri}, "position": {"line": 0, "character": 0}}
    reply = server.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "textDocument/hover", "params": hover}
    )
    assert reply["result"]["contents"]["value"].startswith(count + " ·")


def test_suno_leaves_a_malformed_tag_unsplit():
    from ashugh import suno

    out = suno.format_song("[[Chorus]]\nOh take me home tonight\n", split="all", tags=False)
    assert "[[Chorus]]" in out.text and "to-night" in out.text
