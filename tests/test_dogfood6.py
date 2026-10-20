"""Round six: an assistant following the skill, start to finish."""

from ashugh import fit
from ashugh.spec import from_dict


def requests(text: str, spec: dict) -> dict[int, fit.Request]:
    return {r.line: r for r in fit.requests_for(text, from_dict(spec))}


def test_a_line_is_never_asked_to_rhyme_with_its_own_word():
    text = "Tonight we dance until the light\nAnd hold each other close and tight\n"
    reqs = requests(text, {"language": "en", "rhyme": "AA", "meter": "trochee4"})
    assert reqs[1].rhyme_with == [] and reqs[1].rhyme_sound == "aɪt"  # keep its own rhyme
    assert reqs[2].rhyme_with == ["light"]


def test_a_partner_whose_rhyme_word_must_change_is_no_target():
    text = "Իմ սիրելի արջուկը\nՔնիր, քնիր, իմ բալիկ\n"
    reqs = requests(text, {"language": "hy", "rhyme": "AA", "forbid_final": ["ը"]})
    assert reqs[2].rhyme_with == []
    assert any("L1 must change" in p for p in reqs[2].problems)


def test_the_rhyme_sound_is_the_rime_and_keeps_an_open_rhymes_consonant():
    en = requests("I walk the night\nI hold a cup\n", {"language": "en", "rhyme": "AA"})
    assert en[2].rhyme_sound == "aɪt"  # not naɪt: rhyme on the rime
    ru = requests("Я вижу ты\nПою весной\n", {"language": "ru", "rhyme": "AA"})
    assert ru[2].rhyme_sound == "tɨ"  # ты / красоты: Russian open rhymes need it


def test_a_rhyme_on_the_same_word_is_named_unless_the_line_repeats():
    from ashugh.scan import scan

    spec = from_dict({"language": "en", "rhyme": "AA"})
    rep = scan("Hold me close tonight\nWe will dance tonight\n", spec)
    (warn,) = [i for i in rep.issues if i.code == "rhyme"]
    assert warn.severity == "warning" and warn.line == 2 and "tonight" in warn.message
    assert rep.ok
    refrain = scan("Dance with me tonight\nDance with me tonight\n", spec)
    assert [i for i in refrain.issues if i.code == "rhyme"] == []


def test_suno_spells_the_schwas_the_count_kept():
    from ashugh import suno

    line = "Մայրիկն է քեզ մոտ նստած\n"
    eight = from_dict({"language": "hy", "syllables": 8})
    seven = from_dict({"language": "hy", "syllables": 7})
    assert suno.format_song(line, spec=eight, armenian="schwa", tags=False).text.startswith(
        "Մայրիկըն է"
    )
    assert suno.format_song(line, spec=seven, armenian="schwa", tags=False).text.startswith(
        "Մայրիկն է"
    )
    assert suno.format_song(line, spec=eight, armenian="latin", tags=False).text.startswith(
        "Mayrikən e"
    )


def test_a_meter_that_drops_a_syllable_says_so():
    from ashugh.scan import scan

    rep = scan(
        "Every heartbeat pulls us under\n", from_dict({"language": "en", "meter": "trochee4"})
    )
    notes = [(i.message, i.detail) for i in rep.issues if i.code == "syllables"]
    assert notes == [("fits if «Every» is sung with one syllable fewer", "sung Eve-ry")]


def test_the_found_scheme_shows_endings_where_the_spec_asks_them():
    from ashugh.report import text
    from ashugh.scan import scan

    song = (
        "The river sings tonight\nIn every shining morning\n"
        "I hold the silver light\nAnd hear the distant warning\n"
    )
    rep = scan(song, from_dict({"language": "en", "rhyme": "aBaB"}))
    assert rep.ok and "· aBaB (spec aBaB)" in text(rep, show_all=True)


def test_pick_json_lists_what_it_ignored(tmp_path, capsys):
    import json

    from ashugh.cli import main

    song = tmp_path / "s.txt"
    song.write_text("I walk the way\nI hold the light and more\n", encoding="utf-8")
    cands = tmp_path / "c.json"
    cands.write_text(json.dumps({"2": ["I hold the light"], "9": ["x"]}), encoding="utf-8")
    args = ["--candidates", str(cands), "--syllables", "4", "--json", "--lang", "en"]
    main(["pick", str(song), *args])
    data = json.loads(capsys.readouterr().out)
    assert data["ignored"] == ["line 9 is no lyric line (lines count from the file's first)"]


def test_syl_gives_the_range_a_line_may_count(capsys):
    from ashugh.cli import main

    main(["syl", "--lang", "hy", "նա ստացավ"])
    assert capsys.readouterr().out.split()[0] == "3-4"  # the ը may merge after նա
    main(["syl", "--lang", "en", "every day"])
    assert capsys.readouterr().out.split()[0] == "3-4"  # e-ve-ry or eve-ry
    main(["syl", "--lang", "en", "the day"])
    assert capsys.readouterr().out.split()[0] == "2"


def test_a_line_no_song_would_sing_is_read_as_free_verse_quickly():
    import time

    from ashugh.scan import scan

    start = time.perf_counter()
    rep = scan(" ".join(["love"] * 6000) + "\n")  # 6.7 s before the cap
    assert rep.units[0].meter == "free" and time.perf_counter() - start < 1.5
