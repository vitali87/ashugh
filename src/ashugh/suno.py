"""suno: rewrite lyrics into a form Suno sings the way they are meant.

* Russian: ё is restored where the dictionary is sure (еще -> ещё), and
  stress is marked only on words whose stress is ambiguous or unknown, by a
  capital vowel (зАмок, the convention Suno users rely on) or an acute.
* Armenian: kept in script, written with every sung schwa spelled out
  (ըսպասում, Մըկըրտիչ), or romanized phonetically (əspasum, Məkərtich).
  A probe policy (ashugh probe score) can pick the mode word by word.
* Held notes: the last word of each line, or every word, split into its
  sung syllables (пра-вил).
* Section tags: translated to the names Suno knows ([Припев] -> [Chorus]);
  an untagged song gets [Verse n] and [Chorus] from its repeated stanzas.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import lang as languages
from . import lyrics, rhyme
from .lang import en, hy, ru
from .model import ACUTE, LICENCES, Word
from .scan import LineReport, Report, scan
from .spec import Spec

STRESS_MODES = ("caps", "acute", "none")
ARMENIAN_MODES = ("script", "schwa", "latin")
SPLIT_MODES = ("none", "last", "all")
RUSSIAN_PROBES = ("plain", "caps", "acute")  # probe modes, mapped to stress marks below
PROBE_STRESS = {"plain": "none", "caps": "caps", "acute": "acute"}
RU_VOWELS = set("аеёиоуыэюя")

LATIN = {
    "a": "a",
    "e": "e",
    "i": "i",
    "o": "o",
    "u": "u",
    "b": "b",
    "g": "g",
    "d": "d",
    "z": "z",
    "tʰ": "t",
    "ʒ": "zh",
    "l": "l",
    "χ": "kh",
    "ts": "ts",
    "k": "k",
    "h": "h",
    "dz": "dz",
    "ʁ": "gh",
    "tʃ": "ch",
    "m": "m",
    "j": "y",
    "n": "n",
    "ʃ": "sh",
    "tʃʰ": "ch",
    "p": "p",
    "dʒ": "j",
    "r": "rr",
    "s": "s",
    "v": "v",
    "t": "t",
    "ɾ": "r",
    "tsʰ": "ts",
    "pʰ": "p",
    "kʰ": "k",
    "f": "f",
}


@dataclass
class Note:
    line: int
    kind: str  # yo | stress | armenian | split | tag | spelled
    word: str
    new: str
    why: str = ""


@dataclass
class SunoResult:
    text: str
    notes: list[Note] = field(default_factory=list)


def load_policy(path: str | Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"{path}: {e}") from None
    check_policy(data)
    return data


def check_policy(policy: dict) -> None:
    if not isinstance(policy, dict):
        raise ValueError("a policy is an object keyed by language")
    for lang, allowed, fallback in (
        ("hy", ARMENIAN_MODES, "script"),
        ("ru", RUSSIAN_PROBES, "plain"),
    ):
        entry = policy.get(lang, {})
        if not isinstance(entry, dict):
            raise ValueError(f'policy "{lang}" must be an object')
        words = entry.get("words") or {}
        if not isinstance(words, dict):
            raise ValueError(f'policy "{lang}" words must map words to modes')
        modes = [entry.get("default", fallback), *words.values()]
        bad = [m for m in modes if not isinstance(m, str) or m not in allowed]
        if bad:
            raise ValueError(f"{lang} policy modes must be {', '.join(allowed)}, not {bad[0]!r}")


def format_song(
    text: str,
    spec: Spec | None = None,
    stress: str = "caps",
    armenian: str = "script",
    split: str = "none",
    schwa: str = "ə",
    tags: bool = True,
    policy: dict | None = None,
    lang: str | None = None,
) -> SunoResult:
    if stress not in STRESS_MODES:
        raise ValueError(f"stress must be one of {', '.join(STRESS_MODES)}")
    if armenian not in ARMENIAN_MODES:
        raise ValueError(f"armenian must be one of {', '.join(ARMENIAN_MODES)}")
    if split not in SPLIT_MODES:
        raise ValueError(f"split must be one of {', '.join(SPLIT_MODES)}")
    if not schwa or not schwa.isalpha():
        raise ValueError("schwa must be a letter, e.g. ə or e")
    if policy is not None:
        check_policy(policy)
    text = lyrics.clean(text)
    words_policy = ((policy or {}).get("hy") or {}).get("words") or {}
    default_mode = ((policy or {}).get("hy") or {}).get("default", armenian) if policy else armenian
    ru_words: dict[str, str] = {}
    if policy and "ru" in policy:
        stress = PROBE_STRESS[policy["ru"].get("default", "plain")]
        ru_words = {w: PROBE_STRESS[m] for w, m in (policy["ru"].get("words") or {}).items()}

    report = scan(text, spec or Spec(), lang=lang)
    lexicon = (spec or Spec()).lexicon
    raw = lyrics.split_lines(text, keepends=True)
    notes: list[Note] = []
    by_meter = {lr.line.number for u in report.units if u.meter_source == "spec" for lr in u.lines}
    rhymed = _rhymed_spellings(report)
    for lr in report.lines:
        line_raw = raw[lr.line.number - 1]
        body, ending = _split_ending(line_raw)
        spans = lyrics.token_spans(body)
        elided = _elided(lr, lr.target is not None or lr.line.number in by_meter)
        pieces, last = [], 0
        for i, ((a, b, token), word) in enumerate(zip(spans, lr.line.words)):
            pieces.append(body[last:a])
            hold = split == "all" or (split == "last" and i == len(spans) - 1)
            mode = words_policy.get(word.norm, default_mode)
            how = ru_words.get(word.norm, stress)
            prefer = rhymed.get((lr.line.number, i))
            new = _render(word, token, lr, i, i in elided, how, mode, hold, schwa, notes, prefer)
            pieces.append(new)
            last = b
        pieces.append(body[last:])
        line_out = "".join(pieces)
        armenian_line = lr.line.lang == "hy" or any(hy.is_armenian(ch) for ch in line_out)
        if armenian_line and default_mode != "script":
            line_out = _armenian_asides(line_out, words_policy, default_mode, schwa, lexicon)
            line_out = _place_marks(line_out)
        line_out = _russian_asides(line_out, lr.line.number, notes)
        raw[lr.line.number - 1] = line_out + ending
    sung = {lr.line.number for lr in report.lines}
    for k, line_raw in enumerate(raw):  # a line that is only a backing vocal: (օ՜, օ՜)
        if k + 1 in sung or lyrics.is_tag(line_raw) or "(" not in line_raw:
            continue
        body, ending = _split_ending(line_raw)
        if default_mode != "script" and any(hy.is_armenian(ch) for ch in body):
            body = _armenian_asides(body, words_policy, default_mode, schwa, lexicon)
        raw[k] = _russian_asides(body, k + 1, notes) + ending
    out = "".join(raw)
    if tags:
        out = _retag(out, report, notes)
    return SunoResult(out, notes)


ARMENIAN_STOPS = str.maketrans({"։": ".", "՝": ","})


def _armenian_asides(
    line: str, policy: dict, mode: str, schwa: str, lexicon: dict[str, str]
) -> str:
    """The backing vocals in parentheses spelled like the rest of the line, read as a
    line of their own (ո՞ւր ես is you are, not I) with the spec's lexicon, and in
    Latin letters the Armenian full stop and pause as . and ,."""

    def aside(inner: str) -> str:
        spans = lyrics.word_spans(inner)
        words = languages.analyze("hy", [t for _, _, t in spans], lexicon, inner[1:-1])
        if len(words) != len(spans):  # a token the analysis split or joined: word by word
            words = [languages.analyze_word_as(t, lexicon) for _, _, t in spans]
        out, last = [], 0
        for (a, b, token), w in zip(spans, words):
            if not any(hy.is_armenian(ch) for ch in token):
                continue
            how = policy.get(w.norm, mode)
            aux = w.norm == "ես" and w.enclitic  # ո՞ւր ես: [es], not the pronoun
            out += [inner[last:a], _armenian(w, token, False, how, False, schwa, 0, [], aux)]
            last = b
        return _place_marks("".join(out) + inner[last:], aside=True)

    line = lyrics.sub_asides(line, aside)
    if mode == "latin":
        line = line.translate(ARMENIAN_STOPS)
    return line


def _russian_asides(line: str, n: int, notes: list[Note]) -> str:
    """The backing vocals in parentheses with the ё the line would get: моё (моё),
    where only one spelling is a word; no stress marks, which want a meter."""

    def aside(inner: str) -> str:
        out, last = [], 0
        for a, b, token in lyrics.word_spans(inner):
            if not any(ru.is_cyrillic(ch) for ch in token):
                continue
            out += [inner[last:a], _russian(ru.analyze_word(token), token, None, "none", n, notes)]
            last = b
        return "".join(out) + inner[last:]

    return lyrics.sub_asides(line, aside)


def _split_ending(line: str) -> tuple[str, str]:
    stripped = line.rstrip("\r\n")
    return stripped, line[len(stripped) :]


def _elided(lr: LineReport, constrained: bool) -> set[int]:
    """Schwas to drop. Where a count or a meter holds the line, the ones the scan
    dropped, so Suno sings what the check passed (Մայրիկըն է at 8 syllables,
    Մայրիկն է at 7); with nothing to keep, those the scan dropped too, and
    speech's own forms besides: every linking article -ն (Մըկըրտիչն էլ) and
    every leading ը after a vowel (Na statsav). A possessive's schwa the scan
    kept stays (լը-ռու-թյու-նըդ)."""
    if constrained:
        return set(lr.fit.elided)
    words = lr.line.words
    out = set(lr.fit.elided)
    out |= {
        i
        for i, w in enumerate(words)
        if w.lang == "hy"
        and w.drop is not None
        and w.drop == w.size - 1
        and w.size > 1
        and w.norm.endswith("ն")
    }
    # and every leading ը a vowel before swallows (նա ստացավ: նաս-տա-ցավ)
    out |= {i for i, w in enumerate(words) if w.lang == "hy" and w.head_schwa and w.drop == 0}
    return out


def _render(
    w: Word,
    token: str,
    lr: LineReport,
    i: int,
    dropped: bool,
    stress: str,
    mode: str,
    hold: bool,
    schwa: str,
    notes: list[Note],
    prefer: str | None = None,
) -> str:
    n = lr.line.number
    if w.lang == "ru":
        words, chosen = lr.line.words, lr.fit.stresses
        nxt = i + 1
        if (
            stress != "none"
            and nxt < len(words)
            and words[nxt].leans
            and chosen.get(nxt, 0) is None
        ):
            # по́ лесу: the noun gave the preposition its stress (or the writer did)
            new = _mark_vowel(token.replace(ACUTE, ""), 0, stress)
            notes.append(Note(n, "stress", token, new, "stress on the preposition"))
            return new
        if w.spelled:  # СПб as эс-пэ-бэ́: a singer may read the letters as one word
            names = list(ru.letter_names(w.norm))
            if stress != "none":
                names[-1] = _mark_vowel(names[-1], 0, stress)
            new = "-".join(names)
            notes.append(Note(n, "spelled", token, new, "an abbreviation sung letter by letter"))
            return new
        st = chosen.get(i)
        if lr.fit.off_beat and w.ambiguous and w.readings:
            st = w.readings[0].stress  # the line fails its meter anyway: the usual reading
        new = _russian(w, token, st, stress, n, notes, prefer)
        return _hyphenate(new, [len(s.text) for s in w.syllables]) if hold and w.size > 1 else new
    if w.lang == "hy" and languages.LATIN_WITH_ENDING.fullmatch(token):  # TikTok-ում
        if mode != "latin":
            return token
        name, ending = token.split("-", 1)
        phones = tuple(s.ph for s in hy.segments("ա" + ending)[1:])
        if w.syllables[-1].text == "ը" + ending:  # iPhone-ս, iPhone-əs
            phones = ("ə", *phones)
        new = f"{name}-{_latin(phones, False, schwa)}"
        notes.append(Note(n, "armenian", token, new, "latin"))
        return new
    if w.lang == "hy" and w.spelled:  # ԱՄՆ as Ա-Մե-Նե, A-Me-Ne
        if mode == "latin":
            new = "-".join(  # the letters' names capitalized, an ending not: A-Me-Ne-its
                _latin(s.phones, False, schwa).capitalize()
                if s.text[:1].isupper()
                else _latin(s.phones, False, schwa)
                for s in w.syllables
            )
        else:
            new = "-".join(s.text for s in w.syllables)
        notes.append(Note(n, "spelled", token, new, "an abbreviation sung letter by letter"))
        return new
    if w.lang == "hy":
        prev = lr.line.words[i - 1] if i > 0 else None
        linked = prev is not None and prev.lang == "hy" and prev.drop == prev.size - 1
        after_link = linked and w.norm in hy.AUXILIARIES  # լույսն ես: [es], not the pronoun
        # The line's analysis tells the auxiliary ես (գեղեցիկ ես, ինչու ես լռում)
        # from the pronoun I (ու ես, Ես եմ, հիմա ես գիտեմ).
        after_link = after_link or (w.norm == "ես" and w.enclitic)
        return _armenian(w, token, dropped, mode, hold, schwa, n, notes, after_link)
    if hold and w.size > 1:
        if w.spelled:  # WTF as W-T-F, DMs as D-Ms: the letters, each sung by its name
            return "-".join(s.text for s in w.syllables).replace("(dou-ble-u)", "")
        pieces = [s.text for s in w.syllables]
        if "".join(pieces) != token:
            return token  # pieces the spelling cannot give (W, etc): Suno reads it whole
        short = dropped or i in lr.fit.elided  # the meter's own short form, count or not
        return "-".join(en.sung_pieces(pieces, w.drop, short))
    return token


def _rhymed_spellings(report: Report) -> dict[tuple[int, int], str]:
    """(line, word) -> the spelling of the reading a line's rhyme word rhymes in:
    поёшь, not поешь, where its partner is найдёшь."""
    out = {}
    for unit in report.units:
        for lr in unit.lines:
            partners = [
                o for o in unit.lines if o is not lr and lr.letter and o.letter == lr.letter
            ]
            w = rhyme.anchor_word(lr.line, lr.fit)
            if not partners or w is None or len(lr.tails) < 2:
                continue
            s, tail, _ = max((rhyme.match(lr.tails, o.tails) for o in partners), key=lambda m: m[0])
            if s > 0 and tail is not None:
                out[lr.line.number, w] = tail.spelling.split(" ")[0]
    return out


def _russian(
    w: Word,
    token: str,
    chosen: int | None,
    stress: str,
    n: int,
    notes: list[Note],
    prefer: str | None = None,
) -> str:
    token = ru.APOSTROPHE_MARK.sub("\\1" + ACUTE, token)  # замо'к: the writer's mark
    if ACUTE in token and stress == "none":
        return token  # the writer's own marks stay as written
    letters = token.replace(ACUTE, "")
    marked_by_writer = letters != token
    candidates = [r for r in w.readings if r.stress == chosen] or list(w.readings)
    candidates = [r for r in candidates if r.spelling == prefer] or candidates  # the rhyme's
    # The readings of the stress the line chose: звёзды, not звезды́, is the one
    # sung on the first syllable, so its ё goes back even though both are words.
    spellings = {r.spelling for r in candidates if r.source not in LICENCES}
    spellings = spellings or {r.spelling for r in candidates}
    new = letters
    if len(spellings) == 1 and "ё" in (only := next(iter(spellings))):
        target = only.replace("-", "")
        flat = [k for k, ch in enumerate(letters) if ch != "-"]
        if len(flat) == len(target):
            chars = list(letters)
            for k, ch in zip(flat, target):
                if ch == "ё" and chars[k].lower() == "е":
                    chars[k] = "Ё" if chars[k].isupper() else "ё"
            if "".join(chars) != letters:
                new = "".join(chars)
                notes.append(Note(n, "yo", token, new, "ё restored"))
    hint = w.ambiguous or w.guessed or marked_by_writer
    if (
        not marked_by_writer
        and "-" in w.norm
        and all(ru.vowel_count(p) <= 1 for p in w.norm.split("-"))
    ):
        hint = False  # жил-был, раз-два-три: every part takes its own stress
    if stress != "none" and w.size > 1 and chosen is not None and hint:
        marked = _mark_vowel(new, chosen, stress)
        if marked != new:
            if marked_by_writer:
                why = "marked in the lyrics"
            else:
                why = "stress guessed by the meter" if w.guessed else "ambiguous stress"
            notes.append(Note(n, "stress", token, marked, why))
            new = marked
    return new


def _mark_vowel(token: str, syllable: int, stress: str) -> str:
    count = -1
    for k, ch in enumerate(token):
        if ch.lower() in RU_VOWELS:
            count += 1
            if count == syllable:
                if ch.lower() == "ё":
                    return token
                if stress == "caps" and k > 0 and not token.isupper():
                    return token[:k] + ch.upper() + token[k + 1 :]
                # a capital first letter reads as case, and in a word in capitals a
                # capital marks nothing: the acute does (ЗАМО́К)
                return token[: k + 1] + ACUTE + token[k + 1 :]
    return token


def _hyphenate(token: str, lengths: list[int]) -> str:
    """Hyphens between sung syllables; lengths count letters, not marks or hyphens."""
    cuts, total = set(), 0
    for length in lengths[:-1]:
        total += length
        cuts.add(total)
    out, seen = [], 0
    for ch in token:
        if ch not in (ACUTE, "-") and seen in cuts and out and out[-1] != "-":
            out.append("-")
            cuts.discard(seen)
        out.append(ch)
        if ch not in (ACUTE, "-"):
            seen += 1
    return "".join(out)


def _armenian(
    w: Word,
    token: str,
    dropped: bool,
    mode: str,
    hold: bool,
    schwa: str,
    n: int,
    notes: list[Note],
    after_link: bool = False,
) -> str:
    drop = w.drop if dropped else None
    if mode == "script" and token[:1].isascii():  # Mtnem qo: Armenian typed in Latin
        return _latin_typed(w, token, hold, n, notes)
    if mode == "latin" and lyrics.held_note(w.norm, "աեէըիոօ"):  # Օօօ: Ooo, held
        new = _case_like(token, _latin(w.syllables[0].phones, False, schwa) * len(w.norm))
        notes.append(Note(n, "armenian", token, new, mode))
        return new
    if mode == "latin":
        parts = [_latin(s.phones, k == drop, schwa) for k, s in enumerate(w.syllables)]
        if after_link and parts and parts[0].startswith("y"):
            parts[0] = parts[0][1:]
    elif mode == "schwa":
        parts = [_written(s.text, True) if k == drop else s.text for k, s in enumerate(w.syllables)]
    else:
        parts = [_written(s.text, s.epenthetic) for s in w.syllables]
    mark = next((ch for ch in token if ch in hy.STRESS_MARKS), None)
    stressed = w.readings[0].stress if mark and w.readings else None
    if mark and stressed is not None and stressed < len(parts):
        parts[stressed] = _put_mark(parts[stressed], mark, mode)  # the writer's own stress
    groups = []  # by the writer's hyphenated parts: Սայաթ-Նովեն, Sayat-Noven
    for piece, group in _by_part(w, token, parts):
        joined = ("-" if hold else "").join(_merge_vowelless(group, mode))
        groups.append(_case_like(piece, joined) if mode == "latin" else joined)
    new = "-".join(groups)
    if mode != "latin" and "և" in token.lower():
        new = _ligatures(token, new)
    if mode == "latin":
        if mark in LATIN_MARKS:
            new += SENTENCE_MARKS[mark]  # ո՞ւր: its sentence is a question
    if mode == "script" and not hold:
        return token
    if new != token:
        notes.append(Note(n, "armenian" if mode != "script" else "split", token, new, mode))
    return new


# ՞ and ՜ sit on the stressed vowel of a question or an exclamation; in Latin
# letters the ? or ! goes to the end of the sentence, held meanwhile by a sign.
LATIN_MARKS = {"\u055e": "?", "\u055c": "!"}
SENTENCE_MARKS = {"\u055e": "\x01", "\u055c": "\x02"}
PENDING = {"\x01": "?", "\x02": "!"}
ARMENIAN_VOWEL_LETTERS = set("աեէըիոօևԱԵԷԸԻՈՕ")


def _put_mark(syllable: str, mark: str, mode: str) -> str:
    """The stress mark back on the syllable's vowel: ՛ ՜ ՞ in Armenian letters, an
    acute in Latin ones."""
    latin = mode == "latin"
    vowels = set("aeiouəAEIOU") if latin else ARMENIAN_VOWEL_LETTERS
    for k, ch in enumerate(syllable):
        if ch in vowels:
            return syllable[: k + 1] + (ACUTE if latin else mark) + syllable[k + 1 :]
    return syllable


def _place_marks(text: str, aside: bool = False) -> str:
    """Each pending ? or ! at the end of its sentence: Úr es, úr? and Úr es? Yek. A
    question outranks an exclamation before it (Ó, im ser, úr es?); a backing vocal
    keeps its mark inside its parentheses, and a line ending on one puts its own
    mark before it."""
    out, pending = [], ""
    for k, ch in enumerate(text):
        if ch in PENDING:
            pending = "?" if PENDING[ch] == "?" else (pending or PENDING[ch])
            continue
        rest = text[k + 1 :].lstrip(" ")
        if pending and ch == "." and rest[:1] == ".":
            out.append(pending + ch)  # yó!...: the dots keep their number
            pending = ""
            continue
        if pending and ch == "," and rest[:1] in ("—", "–") and rest:
            out.append(pending)  # Óv e mez pahum? — hartsnum: the quoted words end there
            pending = ""
            continue
        if pending and ch in ".?!":
            out.append(pending if ch == "." else ch)
            pending = ""
            continue
        out.append(ch)
    line = "".join(out)
    if pending:  # at the line's end: in place of a comma, inside a closing quote
        body = line.rstrip()
        end = line[len(body) :]
        if not aside and body.endswith(")") and "(" in body:
            at = body.rindex("(")  # Úr es? (im ser): the backing vocal has its own
            end, body = " " + body[at:] + end, body[:at].rstrip()
        closing = "»”\"’')" if aside else "»”\"’'"
        quote = body[len(body.rstrip(closing)) :]
        body = body[: len(body) - len(quote)].rstrip().rstrip(",;:").rstrip()
        line = body + pending + quote + end
    return line


def _by_part(w: Word, token: str, parts: list[str]) -> list[tuple[str, list[str]]]:
    """The syllables' parts grouped by the hyphenated parts of the word as written
    (Սայաթ-Նովեն: Սա յաթ | Նո վեն); one group if they do not line up."""
    pieces = token.split("-")
    if len(pieces) == 1 or len(parts) != len(w.syllables):
        return [(token, parts)]
    groups: list[tuple[str, list[str]]] = []
    current: list[str] = []
    seen = bound = 0
    for syllable, part in zip(w.syllables, parts):
        current.append(part)
        seen += _letters(_written(syllable.text, syllable.epenthetic))
        if len(groups) < len(pieces) - 1:
            bound_here = bound + _letters(pieces[len(groups)])
            if seen == bound_here:
                groups.append((pieces[len(groups)], current))
                current, bound = [], bound_here
    groups.append((pieces[len(groups)], current))
    return groups if len(groups) == len(pieces) and all(g for _, g in groups) else [(token, parts)]


def _latin_typed(w: Word, token: str, hold: bool, n: int, notes: list[Note]) -> str:
    """A word of Armenian typed in Latin, in script mode: as the writer typed it
    (qo, kyanqs), cut into its syllables when asked (ka-ro-tum)."""
    sizes = [len(s.text.replace("ə", "")) for s in w.syllables]  # the schwas unwritten
    if not hold or sum(sizes) != len(token):
        return token
    cuts = [sum(sizes[:k]) for k in range(len(sizes) + 1)]
    pieces = _merge_vowelless([token[a:b] for a, b in zip(cuts, cuts[1:])], "latin")
    new = "-".join(pieces)
    if new != token:
        notes.append(Note(n, "split", token, new, "script"))
    return new


def _ligatures(token: str, new: str) -> str:
    """The written word's և back where its halves ե and վ meet unbroken in the
    rewritten one (արեվըն is արևըն; Ե-րե-վան, split at a hyphen, stays)."""
    out, i, j = [], 0, 0
    while j < len(new):
        ch = token[i] if i < len(token) else ""
        if ch.lower() == "և" and new[j : j + 2].lower() == "եվ":
            out.append(ch)
            i, j = i + 1, j + 2
        elif new[j] == ch:
            out.append(ch)
            i, j = i + 1, j + 1
        else:  # a schwa written out, a hyphen
            out.append(new[j])
            j += 1
    return "".join(out)


def _letters(text: str) -> int:
    """Letters, և as the two it is drawn for (Երևան: Ե-րե-վան)."""
    return sum(2 if ch == "և" else ch.isalpha() for ch in text)


def _written(text: str, epenthetic: bool) -> str:
    """A syllable as written: its hidden ը taken back out, a capital Ը leaving its
    capital to the letter after it (Ըս-տե: Ստե)."""
    if not epenthetic:
        return text
    if text.startswith("Ը"):
        return text[1:2].upper() + text[2:]
    return text.replace("ը", "", 1)


def _latin(phones: tuple[str, ...], dropped: bool, schwa: str) -> str:
    out = []
    for ph in phones:
        if ph == "ə":
            if not dropped:
                out.append(schwa)
            continue
        out.append(LATIN.get(ph, ph))
    return "".join(out)


def _merge_vowelless(parts: list[str], mode: str) -> list[str]:
    vowels = "aeiouəy" if mode == "latin" else "աեէըիոօւև"
    merged: list[str] = []
    for p in parts:
        has_vowel = any(ch.lower() in vowels for ch in p)
        if merged and not has_vowel:
            merged[-1] += p
        elif not merged or any(ch.lower() in vowels for ch in merged[-1]):
            merged.append(p)
        else:
            merged[-1] += p
    return [p for p in merged if p]


def _case_like(token: str, latin: str) -> str:
    letters = [ch for ch in token if ch.isalpha()]
    if letters and all(ch.isupper() for ch in letters) and len(letters) > 1:
        return latin.upper()
    if token[:1].isupper():
        return latin[:1].upper() + latin[1:]
    return latin


def _retag(text: str, report: Report, notes: list[Note]) -> str:
    raw = lyrics.split_lines(text, keepends=True)
    tagged = False
    for k, line in enumerate(raw):
        if not lyrics.is_tag(line):
            continue
        tagged = True
        new = lyrics.retag(line)  # Suno's names and repeat mark: [Chorus x2]
        if new != line:
            notes.append(Note(k + 1, "tag", line.strip(), new.strip()))
            raw[k] = new
    if tagged or not report.lines:
        return "".join(raw)
    return _infer_tags(raw, report, notes)


def _infer_tags(raw: list[str], report: Report, notes: list[Note]) -> str:
    stanzas: dict[int, list[LineReport]] = {}
    for lr in report.lines:
        stanzas.setdefault(lr.line.unit, []).append(lr)
    texts = {  # the words alone: a last chorus may end on ! or spell вернется for вернётся
        u: tuple(" ".join(lyrics.tokenize(lr.line.text.lower().replace("ё", "е"))) for lr in lrs)
        for u, lrs in stanzas.items()
    }
    repeated = {t for t in texts.values() if list(texts.values()).count(t) > 1}
    verses = sum(1 for t in texts.values() if t not in repeated)
    if repeated:
        why_verse = "a stanza that does not come back is a verse"
    elif len(stanzas) > 1:
        why_verse = "untagged lyrics where no stanza repeats: each a verse"
    else:
        why_verse = "untagged lyrics of one stanza: a verse"
    starts: dict[int, tuple[str, str]] = {}
    verse_no = 0
    for u, lrs in stanzas.items():
        if texts[u] in repeated:
            tag, why = "[Chorus]", "a stanza that comes back is the chorus"
        else:
            verse_no += 1
            tag, why = (f"[Verse {verse_no}]" if verses > 1 else "[Verse]"), why_verse
        starts[lrs[0].line.number] = (tag, why)
    out = []
    for k, line in enumerate(raw, 1):
        if k in starts:
            tag, why = starts[k]
            ending = line[len(line.rstrip("\r\n")) :] or "\n"  # the file's own line endings
            out.append(tag + ending)
            notes.append(Note(k, "tag", "", tag, why))
        out.append(line)
    return "".join(out)
