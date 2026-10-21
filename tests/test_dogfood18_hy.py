"""Round 18 of dogfooding, Armenian: what a songwriter found wrong."""

import pytest

from ashugh import lyrics, probe, suno
from ashugh.fit import replace_lines
from ashugh.scan import analyze_lines, scan
from ashugh.spec import Spec, SpecError, from_dict


def latin(text: str) -> str:
    return suno.format_song(text, armenian="latin", tags=False).text


def test_latin_mode_leaves_no_control_character_and_keeps_the_question():
    out = latin("Ի՜նչ լավ ես, I love you so.\nՈ՞ւր ես, baby, where are you now\n")
    assert "\x01" not in out and "\x02" not in out
    assert out.splitlines()[1].endswith("?")


@pytest.mark.parametrize("mark", ["(2 անգամ)", "(կրկնել)", "(2 раза)"])
@pytest.mark.parametrize("mode", ["script", "schwa", "latin"])
def test_an_armenian_repeat_mark_writes_the_line_out(mark, mode):
    out = suno.format_song(f"Արի, արի {mark}\n", armenian=mode, tags=False).text
    lines = out.splitlines()
    assert len(lines) == 2 and lines[0] == lines[1] and "(" not in out


@pytest.mark.parametrize("voice", ["Կանացի ձայն", "Երգչախումբ", "Женский вокал", "Хор"])
def test_a_voice_tag_keeps_the_section_it_follows(voice):
    spec = from_dict({"language": "hy", "syllables": 8, "section": {"verse": {"syllables": 4}}})
    report = scan(f"[Տուն 2]\n[{voice}]\nԵս գնում եմ\n", spec)
    assert report.ok, report.lines[0].issues


def test_a_voice_beside_a_section_tag_does_not_name_it():
    spec = from_dict({"language": "hy", "syllables": 9, "section": {"chorus": {"syllables": 3}}})
    assert scan("[Կանացի ձայն] [Կրկներգ]\nԱրի տուն\n", spec).ok


def test_the_armenian_apostrophe_is_an_apostrophe():
    (ln,) = analyze_lines("Կ՚երթամ, ս՚իրար", Spec(language="hy"))
    assert [w.size for w in ln.words] == [2, 2]
    assert latin("Կ՚երթամ հեռու\n").startswith("Kertam")


def test_a_lexicon_entry_may_glide_i():
    spec = from_dict({"language": "hy", "syllables": 8, "lexicon": {"Կիլիկիա": "Կի-լի-կյա"}})
    assert scan("Ցանկամ տեսնել իմ Կիլիկիա,\n", spec).ok


def test_a_one_syllable_ia_tells_how_to_write_the_glide():
    with pytest.raises(SpecError, match="յ"):
        from_dict({"language": "hy", "lexicon": {"Կիլիկիա": "Կի-լի-կիա"}})


def test_a_glide_entry_must_still_spell_its_word():
    with pytest.raises(SpecError, match="different word"):
        from_dict({"language": "hy", "lexicon": {"Կիլիկիա": "Կի-լի-կյո"}})


@pytest.mark.parametrize("word", ["կրկներգ", "chorus", "припев"])
def test_syl_analyzes_a_section_name_as_a_word(word, capsys):
    from ashugh.cli import main

    main(["syl", word])
    assert capsys.readouterr().out.strip()


def test_rhyme_takes_section_names_as_words(capsys):
    from ashugh.cli import main

    assert main(["rhyme", "chorus", "porous"]) == 0
    assert "perfect" in capsys.readouterr().out


def test_a_song_still_takes_a_bare_section_name_as_its_tag():
    lines = analyze_lines("Chorus:\nStay with me tonight\n", Spec(language="en"))
    assert [ln.text for ln in lines] == ["Stay with me tonight"]


def test_probe_spells_a_section_name_in_every_mode():
    plan = probe.make_probes(["կրկներգ"], "hy")
    assert len(plan) == 3
    assert any(p.lyrics.count("kərknerg") for p in plan)


def test_an_armenian_translation_ends_on_the_armenian_full_stop():
    out = replace_lines(
        "Where are you going, my love?\nWho are you!\nThe wind;\nLike diamond and love.\n",
        {
            1: "Ո՞ւր ես գնում, իմ սեր",
            2: "Ո՞վ ես դու",
            3: "Ձյուն է պտտում քամին",
            4: "Inchpes adamand u ser",
        },
        lang="hy",
    )
    assert out.splitlines() == [
        "Ո՞ւր ես գնում, իմ սեր։",
        "Ո՞վ ես դու։",
        "Ձյուն է պտտում քամին։",
        "Inchpes adamand u ser.",
    ]


class Bank:
    name = "bank"

    def __init__(self):
        self.calls = []

    def propose(self, requests):
        self.calls.append(list(requests))
        return {r.id: [] for r in requests}


@pytest.mark.parametrize(
    "text,target,script", [("Ես քեզ սիրում եմ\n", "en", ""), ("I love you\n", "hy", "armenian")]
)
def test_a_translation_request_names_the_targets_letters(text, target, script):
    from ashugh import translate

    bank = Bank()
    translate.translate_song(text, target, bank, keep={"syllables"}, rounds=1)
    assert bank.calls[0][0].script == script


def test_a_marked_a_is_an_interjection():
    (ln,) = analyze_lines("Ա՜խ, իմ սեր, ա՜", Spec(language="hy"))
    assert not ln.words[-1].enclitic
    assert scan("Ա՜խ, իմ սեր, ա՜\n", from_dict({"language": "hy", "endings": "m"})).ok


def test_the_auxiliary_a_still_leans():
    (ln,) = analyze_lines("Իմ սերն ա", Spec(language="hy"))
    assert ln.words[-1].enclitic


@pytest.mark.parametrize("text,count", [("Տէր, ողորմեա", 4), ("ցոյց", 1), ("բոյս", 1)])
def test_classical_spellings_reformed(text, count):
    (ln,) = analyze_lines(text, Spec(language="hy"))
    assert sum(w.size for w in ln.words) == count


def test_tsoyts_rhymes_with_tsuyts():
    lines = analyze_lines("ցոյց\nցույց", Spec(language="hy"))
    assert lines[0].words[0].readings[0].phones == lines[1].words[0].readings[0].phones


@pytest.mark.parametrize("word,count", [("An@ndhat", 3), ("Sirt@s", 2)])
def test_a_mid_word_at_is_a_schwa(word, count):
    assert lyrics.tokenize(f"{word} qez em sirum")[0] == word
    (ln,) = analyze_lines(f"{word} qez em sirum", Spec(language="hy"))
    assert ln.words[0].size == count


def test_an_email_address_is_no_armenian_word():
    assert "a@b" not in lyrics.tokenize("write me at a@b.com")


@pytest.mark.parametrize(
    "tag,suno_tag",
    [("Ասմունք", "Spoken Word"), ("Գործիքային", "Instrumental"), ("Речь", "Spoken Word")],
)
def test_armenian_and_russian_spoken_and_instrumental_tags(tag, suno_tag):
    assert lyrics.suno_tag(tag) == suno_tag


def test_a_recitation_is_free_of_the_count():
    text = "[Ասմունք]\nԵվ այդ ժամանակ ես հասկացա որ ամեն ինչ փոխվել էր\n"
    assert scan(text, from_dict({"language": "hy", "syllables": 7})).ok


@pytest.mark.parametrize("line", ["Mtnem aygin", "Es qez sirum em"])
def test_a_single_latin_typed_line_is_armenian(line):
    (ln,) = analyze_lines(line, Spec())
    assert ln.lang == "hy"


@pytest.mark.parametrize("line", ["I love you", "WTF"])
def test_a_single_english_line_stays_english(line):
    (ln,) = analyze_lines(line, Spec())
    assert ln.lang == "en"


@pytest.mark.parametrize("vocable", ["Օ-օ-օ", "Ու-ու-ու", "Ա-ա-ա"])
def test_a_hyphenated_vocable_is_free_notes(vocable):
    (ln,) = analyze_lines(f"{vocable}, {vocable.lower()}", Spec(language="hy"))
    assert len(ln.words) == 2
    w = ln.words[0]
    assert w.size == 3 and not w.clitic and not w.enclitic
    report = scan(
        f"{vocable}, {vocable.lower()}\n", from_dict({"language": "hy", "meter": "trochee"})
    )
    assert not any(
        "off the beat" in i.message and vocable in i.message for i in report.lines[0].issues
    )


def test_a_hyphenated_vocable_is_spelt_in_latin():
    assert latin("Սայաթ-Նովեն երգում է (օ-օ-օ)\n").strip().endswith("(o-o-o)")


@pytest.mark.parametrize("name", ["յամբ4", "քորե", "դակտիլ", "ամֆիբրաքիոս", "անապեստ", "դոլնիկ"])
def test_armenian_meter_names(name):
    from ashugh import meter

    assert meter.parse_meter(name)[0] in meter.METERS
