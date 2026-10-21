"""Armenian, from the ninth dogfooding round, checked against Wiktionary's broad IPA."""

import pytest

from ashugh.lang import hy
from ashugh.scan import scan
from ashugh.spec import from_dict


def sung(word: str) -> str:
    return hy.analyze_word(word).sung()


@pytest.mark.parametrize(
    "word, want",
    [
        ("չգցել", "չը-գը-ցել"),  # /tʃʰəɡətsʰel/
        ("չքսեր", "չը-քը-սեր"),  # /tʃʰəkʰəseɾ/
        ("չգնամ", "չը-գը-նամ"),
        ("չմնաս", "չը-մը-նաս"),
        ("կգնամ", "կը-գը-նամ"),  # the future keeps its stem's schwa as the negative does
        ("կմնաս", "կը-մը-նաս"),
        ("չնչին", "չըն-չին"),  # a root, not չ- with a verb
        ("չքնաղ", "չըք-նաղ"),
        ("կղզի", "կըղ-զի"),
        ("կրկին", "կըր-կին"),
    ],
)
def test_the_negative_and_future_prefixes_keep_the_stems_schwa(word, want):
    assert sung(word) == want


def pronoun(line: str, k: int) -> bool:
    rep = scan(line + "\n", from_dict({"language": "hy"}))
    w = rep.lines[0].line.words[k]
    return w.readings[0].phones[:1] == ("j",)


@pytest.mark.parametrize(
    "line, k",
    [
        ("Ու քեզ անվերջ սիրում եմ ես", 5),
        ("Ով եմ ես", 2),
        ("Քեզ եմ ես սիրում", 2),
        ("Քեզ ես սիրեցի", 1),
        ("Երեկ ես տեսա քեզ", 1),
    ],
)
def test_es_with_a_verb_of_i_is_the_pronoun(line, k):
    assert pronoun(line, k)


@pytest.mark.parametrize("line, k", [("Դու գեղեցիկ ես ամեն անգամ", 2), ("Ինչու ես դու ինձ դեմ", 1)])
def test_es_before_a_word_that_only_ends_like_a_verb_is_the_auxiliary(line, k):
    assert not pronoun(line, k)


@pytest.mark.parametrize(
    "word, want",
    [("բլբլալ", "բըլ-բը-լալ"), ("կլկլալ", "կըլ-կը-լալ"), ("փրփրել", "փըր-փը-րել"),
     ("թրթռում", "թըր-թը-ռում"), ("մռմռալ", "մըռ-մը-ռալ")],
)  # fmt: skip
def test_a_reduplicated_root_keeps_both_its_schwas(word, want):
    assert sung(word) == want


@pytest.mark.parametrize("word, size", [("առնչել", 3), ("ձեռնտու", 3), ("ձեռնպահ", 3)])
def test_rn_before_a_consonant_inside_a_word_takes_a_schwa(word, size):
    assert hy.analyze_word(word).size == size


@pytest.mark.parametrize("word, want", [("կողմնակի", "կողմ-նա-կի"), ("բեղմնավոր", "բեղմ-նա-վոր")])
def test_ghmn_inside_a_word_takes_no_schwa(word, want):
    assert sung(word) == want


@pytest.mark.parametrize(
    "word, want",
    [("շքեղ", "շը-քեղ"), ("շփոթ", "շը-փոթ"), ("զտել", "զը-տել"), ("սպասել", "ըս-պա-սել"),
     ("շտապ", "ըշ-տապ")],
)  # fmt: skip
def test_sh_before_an_aspirate_takes_its_schwa_after(word, want):
    assert sung(word) == want


def test_sh_before_an_aspirate_keeps_its_schwa_after_a_vowel():
    rep = scan("Ու շփոթ է իմ հոգին\n", from_dict({"language": "hy", "syllables": 6}))
    assert not rep.ok  # ու-շը-փոթ-է-իմ-հո-գին is 7


def suno_text(text: str, **kw) -> str:
    from unicodedata import normalize

    from ashugh import suno

    return normalize("NFC", suno.format_song(text, tags=False, **kw).text)


def test_a_backing_vocal_reads_es_in_its_own_context():
    out = suno_text("Իմ սեր (ո՞ւր ես, ո՞ւր)\n", armenian="latin")
    assert out == "Im ser (úr es, úr?)\n"


def test_a_backing_vocal_takes_the_specs_lexicon():
    spec = from_dict({"language": "hy", "lexicon": {"կայսրություն": "կայ-սը-րու-թյուն"}})
    out = suno_text("Մեծ կայսրություն (կայսրություն)\n", armenian="schwa", spec=spec)
    assert out.count("կայսըրություն") == 2


def test_a_question_mark_outranks_an_exclamation_before_it():
    assert suno_text("Օ՜, իմ սեր, ո՞ւր ես\n", armenian="latin") == "Ó, im ser, úr es?\n"


def test_syl_shows_the_optional_article_schwa(capsys):
    from ashugh.cli import main

    main(["syl", "--lang", "hy", "Գիշերն իջավ"])
    assert capsys.readouterr().out.split()[0] == "4-5"
