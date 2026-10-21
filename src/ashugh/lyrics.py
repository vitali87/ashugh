"""Reading a lyrics file: section tags, stanzas, lines, word tokens.

Lyrics follow the Suno conventions: a line like [Verse 1] or [Chorus] opens a
section, a blank line ends a stanza, and text in parentheses is a backing
vocal, so it is left out of the line's count.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Collection

from .model import Line

# A tag line: [Verse 1], with more tags or asides beside it if the writer likes
# ([Verse 1] [Male Vocal], [Chorus] (softly)); a BOM may open the file.
TAG_RE = re.compile(r"^\ufeff?\s*(?:\([^)]*\)\s*)*\[[^\]]*\](?:\s*(?:\[[^\]]*\]|\([^)]*\)))*\s*$")
BRACKET_RE = re.compile(r"\[([^\]]*)\]")
NOTE_RE = re.compile(r"[:\u055d\u0589]|\s+-\s+|\s*[–—]\s*")  # [Verse 2: soft], [Տուն 2՝ ռեփ]
LINE_BREAK_RE = re.compile(r"(\r\n|\r|\n)")
WORD_RE = re.compile(
    r"(?<![^\W_])(?<!\d[-'’])(?>(?:@(?=[^\W\d_]))?"  # @ typed for ը: @nkers, sirt@; not a@b.com
    r"[^\W\d_](?:[^\W\d_]|[\u0301\u055b\u055c\u055e]|[-'’](?=[^\W\d_]))*(?:@(?![^\W_]))?"
    r"(?:(?<=[iI][nN])['’](?![^\W\d_]))?"  # a dropped g: goin', lovin'
    r"(?:(?<=(?<![^\W\d_])(?<!['’])[oO])['’](?![^\W\d_]))?)(?!\d)"  # of: a cup o' tea
    r"|&"  # sung as and, и, և
)  # letters glued to digits ('80s, 4ever, mp3, 2000-х, 80's) are no word: the digits warn
DIGIT_RE = re.compile(r"\d")
# What a paste or another keyboard leaves inside a word: a soft hyphen, zero-width
# spaces and joiners, a word joiner or a stray byte order mark, all unseen; the
# look-alikes of the apostrophe (don´t, don`t, don‘t, don′t, donʼt) and of the
# hyphen (по‐моему, по‑моему).
INVISIBLE_RE = re.compile("[\u00ad\u200b-\u200d\u2060\ufeff]")
LETTER = r"[^\W\d_]"
APOSTROPHE_RE = re.compile(rf"(?<={LETTER})[´`‘′ʼ](?={LETTER})")
HYPHEN_RE = re.compile(rf"(?<={LETTER})[\u2010\u2011\u058a](?={LETTER})")  # and Armenian \u058a


# Section names Suno knows, from their English, Russian and Armenian names.
SECTION_NAMES = {
    "verse": "Verse",
    "куплет": "Verse",
    "տուն": "Verse",
    "chorus": "Chorus",
    "refrain": "Chorus",
    "припев": "Chorus",
    "рефрен": "Chorus",
    "կրկներգ": "Chorus",
    "pre-chorus": "Pre-Chorus",
    "prechorus": "Pre-Chorus",
    "pre chorus": "Pre-Chorus",
    "post chorus": "Post-Chorus",
    "postchorus": "Post-Chorus",
    "предприпев": "Pre-Chorus",
    "bridge": "Bridge",
    "бридж": "Bridge",
    "мост": "Bridge",
    "կամուրջ": "Bridge",
    "intro": "Intro",
    "интро": "Intro",
    "вступление": "Intro",
    "ներածություն": "Intro",
    "outro": "Outro",
    "аутро": "Outro",
    "кода": "Outro",
    "концовка": "Outro",
    "ավարտ": "Outro",
    "եզրափակում": "Outro",
    "hook": "Hook",
    "хук": "Hook",
    "instrumental": "Instrumental",
    "проигрыш": "Instrumental",
    "инструментал": "Instrumental",
    "solo": "Solo",
    "соло": "Solo",
    "break": "Break",
    "брейк": "Break",
    "interlude": "Interlude",
    "интерлюдия": "Interlude",
    "post-chorus": "Post-Chorus",
    "постприпев": "Post-Chorus",
    "пост-припев": "Post-Chorus",
    "пре-припев": "Pre-Chorus",
    "пред-припев": "Pre-Chorus",
    "переход": "Bridge",
    "гитарное соло": "Guitar Solo",
    "guitar solo": "Guitar Solo",
    "rap": "Rap",
    "рэп": "Rap",
    "речитатив": "Rap",
    "финал": "Outro",
    "end": "End",
    "конец": "End",
    "վերջ": "End",
    # Armenian loan and native names
    "կուպլետ": "Verse",
    "պրիպև": "Chorus",  # the studio's words, from припев and chorus
    "քորուս": "Chorus",
    "ռեֆրեն": "Chorus",
    "նախակրկներգ": "Pre-Chorus",
    "բրիջ": "Bridge",
    "ինտրո": "Intro",
    "նախերգանք": "Intro",
    "աութրո": "Outro",
    "վերջերգ": "Outro",
    "վերջաբան": "Outro",
    "նախաբան": "Intro",
    "ռեփ": "Rap",
    "ռեպ": "Rap",
    "սոլո": "Solo",
    "մեներգ": "Solo",
    "նվագ": "Instrumental",
    "соло на гитаре": "Guitar Solo",
}
# Voices, which Suno takes as tags of their own beside a section's, not as one.
VOICE_NAMES = {
    "женский вокал": "Female Vocal",
    "мужской вокал": "Male Vocal",
    "хор": "Choir",
    "կանացի ձայն": "Female Vocal",
    "արական ձայն": "Male Vocal",
    "երգչախումբ": "Choir",
}


# Ordinals in section tags, in English, Russian and Armenian: a number (Второй куплет
# and Verse Two are Verse 2, Chorus II is Chorus 2) or the last section
# (Финальный припев, Վերջին կրկներգ: Final Chorus).
ORDINALS = (
    (r"first|one|i|перв\w*|один|առաջին|մեկ", "1"),
    (r"second|two|ii|втор\w*|два|երկրորդ|երկու", "2"),
    (r"third|three|iii|трет\w*|три|երրորդ|երեք", "3"),
    (r"fourth|four|iv|четв[её]рт\w*|четыре|չորրորդ|չորս", "4"),
    (r"fifth|five|v|пят(?:ый|ая|ое)|пять|հինգերորդ|հինգ", "5"),
    (r"last|final|последн\w*|финальн\w*|заключительн\w*|վերջին|վերջնական|եզրափակիչ", "Final"),
)
ORDINAL_RE = re.compile(
    r"\b(?:(\d+)(?:st|nd|rd|th)|" + "|".join(f"({words})" for words, _ in ORDINALS) + r")\b"
)
REPEAT_RE = re.compile(r"(?<!\w)[xх×]\s*(\d+)\b|\b(\d+)\s*[xх×](?!\w)", re.I)  # x2, 2x, х2


def _ordinal(m: re.Match) -> str:
    if m.group(1):
        return m.group(1)
    return next(value for k, (_, value) in enumerate(ORDINALS) if m.group(k + 2))


def _repeat(m: re.Match) -> str:
    return re.sub("[хХ×]", "x", re.sub(r"\s+", "", m.group(0)))  # as written: x2 or 2x


def _split_note(tag: str) -> tuple[str, str]:
    """A tag's name and the note after it: Verse 2 - Rap is (Verse 2, " - Rap")."""
    masked = re.sub(r"\([^)]*\)", lambda m: " " * len(m.group(0)), tag)
    m = NOTE_RE.search(masked)
    return (tag[: m.start()], tag[m.start() :]) if m else (tag, "")


def section_key(tag: str) -> str:
    """[Verse 2] -> verse, [Pre-Chorus] -> pre-chorus, [Припев x2: тише] -> chorus."""
    name = re.sub(r"\([^)]*\)", " ", _split_note(tag)[0].lower())  # (Female), (x2)
    name = ORDINAL_RE.sub(" ", name)
    name = re.sub(r"(?<!\w)[xх×]\s*\d+\b|\b\d+\s*[xх×](?!\w)|\d+", " ", name)
    name = re.sub(r"[^\w\s-]", " ", name)
    name = re.sub(r"\s+", " ", name).strip() or "default"
    known = SECTION_NAMES.get(name)
    return known.lower() if known else name


def _note(text: str) -> str:
    """A note in a tag as Suno names it when it names a section (Рэп -> Rap), else
    as written (тихо)."""
    return SECTION_NAMES.get(text.strip().lower(), text)


def suno_tag(tag: str) -> str | None:
    """A tag's text as Suno names the section: Финальный припев -> Final Chorus,
    Куплет 1 (тихо) -> Verse 1 (тихо), Կրկներգ (x2) -> Chorus x2; None for a
    section Suno has no name for."""
    head, rest = _split_note(tag)
    notes: list[str] = []
    repeat = ""

    def aside(m: re.Match) -> str:
        nonlocal repeat
        r = REPEAT_RE.fullmatch(m.group(1).strip())
        if r:
            repeat = _repeat(r)
        else:
            notes.append(f"({_note(m.group(1))})")
        return " "

    name = re.sub(r"\(([^)]*)\)", aside, head)
    r = REPEAT_RE.search(name)
    if r:
        repeat = _repeat(r)
        name = name[: r.start()] + " " + name[r.end() :]
    ordinals = [_ordinal(m) for m in ORDINAL_RE.finditer(name.lower())]
    name = ORDINAL_RE.sub(" ", name.lower())
    numbers = re.findall(r"\d+", name) + [o for o in ordinals if o.isdigit()]
    name = " ".join(re.sub(r"\d+", " ", name).split())
    known = SECTION_NAMES.get(name) or VOICE_NAMES.get(name)
    if known is None:
        return None
    parts = ["Final"] if "Final" in ordinals else []
    parts += [known, *numbers[:1], *([repeat] if repeat else []), *notes]
    if not NOTE_RE.sub("", rest).strip():
        rest = ""  # [припев:] -> [Chorus]: a separator with no note after it
    if rest:  # [Куплет 2 - Рэп] -> [Verse 2 - Rap]
        sep = NOTE_RE.match(rest)
        head = rest[: sep.end()] if sep else ""
        head = head.replace("\u055d", ":").replace("\u0589", ":")  # [Կրկներգ՝ մեղմ]: Suno's colon
        body = rest[len(head) :].rstrip()
        note = body.lstrip()
        rest = head + body[: len(body) - len(note)] + _note(note)
    return " ".join(parts) + rest


def is_tag(line: str) -> bool:
    """Whether a line holds tags alone: [Chorus], [Verse 1] [Male Vocal], [Chorus] (softly);
    or names its section in plain text, as lyrics sites do (Chorus:, Repeat Chorus)."""
    return bool(TAG_RE.match(line.rstrip("\r\n"))) or plain_label(line) is not None


# A section named in plain text: Chorus:, Verse 1:, Repeat Chorus, CHORUS x2, Припев:
LABEL_RE = re.compile(
    r"\ufeff?\s*(repeat\s+|повтор(?:ить)?\s+)?([^\W\d_][^\[\]():\u055d\u0589]{0,30}?)"
    r"\s*([:\u055d])?\s*",  # not ։, the Armenian full stop: Վերջ։ is a sung line
    re.IGNORECASE,
)
# Names a line may give alone, with no colon, number or Repeat, and be no lyric: not
# End or Վերջ, Տուն (a house), Break, which a song may sing.
BARE_LABELS = {
    "chorus", "verse", "bridge", "intro", "outro", "refrain", "pre-chorus", "post-chorus",
    "prechorus", "interlude", "instrumental", "припев", "куплет", "бридж", "կրկներգ",
    "կուպլետ", "նախակրկներգ",
}  # fmt: skip


# Section names that are words a line may sing alone, even before a colon (Վերջ:,
# typed for Վերջ։ "It's over"; Տուն: "Home"): a label only with a number or Repeat.
SUNG_NAMES = {"վերջ", "տուն", "end", "конец", "home"}


def plain_label(line: str) -> str | None:
    """The bracketed tag a plain-text section label stands for ([Chorus] for Chorus:),
    or None for a line that is no section's name."""
    m = LABEL_RE.fullmatch(line.rstrip("\r\n"))
    if m is None or suno_tag(m.group(2)) is None:
        return None
    numbered = bool(m.group(1)) or bool(DIGIT_RE.search(m.group(2)))
    name = m.group(2).lower()
    if not numbered and (name in SUNG_NAMES or not m.group(3) and name not in BARE_LABELS):
        return None
    return f"[{m.group(2)}]"


def section_tag(line: str, keep: bool = False) -> str | None:
    """The tag that names a tag line's section: the first Suno knows a name for
    ([Female Vocal] [Chorus] is a chorus), else the first; with keep, a line
    whose tags name no section gives None, so the section it follows goes on
    ([Chorus], then [Female Vocal] on a line of its own). None for a lyric line."""
    if not is_tag(line):
        return None
    names = BRACKET_RE.findall(plain_label(line) or line)
    known = [n for n in names if suno_tag(n) is not None]
    if known:
        return known[0]
    return None if keep else names[0]


def retag(line: str) -> str:
    """A tag line with its sections named as Suno names them; any other line as it is."""
    body = line.rstrip("\r\n")
    if not is_tag(body):
        return line
    label = plain_label(body)
    if label is not None:  # Chorus: as [Chorus], which Suno does not sing
        return retag(label) + line[len(body) :]

    def named(m: re.Match) -> str:
        name = suno_tag(m.group(1))
        return m.group(0) if name is None else f"[{name}]"

    return BRACKET_RE.sub(named, body) + line[len(body) :]


# Letters that look alike in Latin and Cyrillic: a stray one in a word of the
# other alphabet (oкон with a Latin o, hеllo with a Cyrillic е) is its twin.
LATIN_TWINS = "aceopxykABCEHKMOPTXY"
CYRILLIC_TWINS = "асеорхукАВСЕНКМОРТХУ"
TO_CYRILLIC = str.maketrans(LATIN_TWINS, CYRILLIC_TWINS)
TO_LATIN = str.maketrans(CYRILLIC_TWINS, LATIN_TWINS)
LETTERS_RE = re.compile(LETTER + "+")


def _twins(m: re.Match) -> str:
    """A word of one alphabet with look-alikes from the other written in its own.
    The alphabet is the one with a letter that has no twin (л in мoлoкo), else
    the one with more letters (МОСКBА); a word with such letters in both stays
    (VIPовский), and so does a run of twins at an edge, a loan (SMSка)."""
    word = m.group(0)
    latin = [k for k, ch in enumerate(word) if ch.isascii()]
    cyrillic = [k for k, ch in enumerate(word) if "\u0400" <= ch <= "\u04ff"]
    if not latin or not cyrillic:
        return word
    latin_own = any(word[k] not in LATIN_TWINS for k in latin)
    cyrillic_own = any(word[k] not in CYRILLIC_TWINS for k in cyrillic)
    if latin_own == cyrillic_own and (latin_own or len(latin) == len(cyrillic)):
        return word
    to_cyrillic = cyrillic_own if latin_own != cyrillic_own else len(cyrillic) > len(latin)
    few, table = (latin, TO_CYRILLIC) if to_cyrillic else (cyrillic, TO_LATIN)
    run = few == list(range(few[0], few[-1] + 1))
    if len(few) > 1 and run and (few[0] == 0 or few[-1] == len(word) - 1):
        return word
    return "".join(ch.translate(table) if k in few else ch for k, ch in enumerate(word))


# A grave on a Cyrillic vowel, which dictionaries put on a secondary stress and
# writers on any (мѝлый, за̀мок): a stress mark like the acute. е and и with it
# compose into letters of their own (ѐ, ѝ), which are taken apart first. And the
# Armenian presentation ligatures of old fonts and PDFs, as the letters they draw.
ARMENIAN_LIGATURES = str.maketrans({"ﬓ": "մն", "ﬔ": "մե", "ﬕ": "մի", "ﬖ": "վն", "ﬗ": "մխ"})
GRAVE_LETTERS = str.maketrans({"ѐ": "е\u0301", "ѝ": "и\u0301", "Ѐ": "Е\u0301", "Ѝ": "И\u0301"})
GRAVE_RE = re.compile("([аеёиоуыэюяАЕЁИОУЫЭЮЯ])\u0300")


def clean(text: str) -> str:
    """Text as the tools read it: letters composed (е with a combining diaeresis is
    ё, as an editor shows it), unseen characters gone, a stray letter of the
    other alphabet written as its twin, and the look-alikes of the apostrophe
    and the hyphen inside a word written ' and -. Lines stay where they are, so
    a report's line numbers are the file's."""
    if text.isascii() and "`" not in text:
        return text
    text = INVISIBLE_RE.sub("", unicodedata.normalize("NFC", text))
    text = text.translate(GRAVE_LETTERS).translate(ARMENIAN_LIGATURES)
    text = GRAVE_RE.sub("\\1\u0301", text)
    text = LETTERS_RE.sub(_twins, text)
    return HYPHEN_RE.sub("-", APOSTROPHE_RE.sub("'", text))


def split_lines(text: str, keepends: bool = False) -> list[str]:
    """Lines as editors count them: only \\n, \\r\\n and \\r end a line, not U+2028."""
    parts = LINE_BREAK_RE.split(text)
    lines = [parts[i] + (parts[i + 1] if keepends else "") for i in range(0, len(parts) - 1, 2)]
    if parts[-1]:
        lines.append(parts[-1])
    return lines


def tokenize(text: str) -> list[str]:
    return [t for _, _, t in token_spans(text)]


def word_spans(text: str) -> list[tuple[int, int, str]]:
    """(start, end, token) of every word, parentheses or not."""
    return [(m.start(), m.end(), m.group(0)) for m in WORD_RE.finditer(text)]


def aside_spans(text: str) -> list[tuple[int, int]]:
    """(start, end) of each backing vocal: text in parentheses, with any that sit
    inside it ((and twinkle (on the) milky way) is one); a ( never closed, or a )
    never opened, is no aside."""
    opened, spans = [], []
    for k, ch in enumerate(text):
        if ch == "(":
            opened.append(k)
        elif ch == ")" and opened:
            spans.append((opened.pop(), k + 1))
    out: list[tuple[int, int]] = []
    for a, b in sorted(spans):
        if not out or a >= out[-1][1]:  # not inside the one before
            out.append((a, b))
    return out


def sub_asides(text: str, fn: Callable[[str], str]) -> str:
    """text with each backing vocal, parentheses and all, replaced by fn of it."""
    out, last = [], 0
    for a, b in aside_spans(text):
        out += [text[last:a], fn(text[a:b])]
        last = b
    return "".join(out) + text[last:]


def token_spans(text: str) -> list[tuple[int, int, str]]:
    """(start, end, token) of every word outside parentheses, as tokenize sees them."""
    masked = sub_asides(text, lambda aside: " " * len(aside))
    spans = []
    for m in WORD_RE.finditer(masked):
        parts = m.group(0).split("-")
        if len(parts) > 1 and len({p.lower() for p in parts}) == 1 and len(parts[0]) > 1:
            # a reduplication is one word per part, each with its own stress: тихо-тихо
            # (but о-о-о is one sung vowel, not a row of clitics)
            at = m.start()
            for p in parts:
                spans.append((at, at + len(p), p))
                at += len(p) + 1
        else:
            spans.append((m.start(), m.end(), m.group(0)))
    return spans


# A repeat mark that ends a line (Я жду тебя х2!, I go 2x) is no number to sing.
REPEAT_END_RE = re.compile(r"(?<!\w)(?:[xх×]\s*\d+|\d+\s*[xх×])(?!\w)[\s.!?,…]*$", re.I)


def has_digits(text: str) -> bool:
    return bool(DIGIT_RE.search(REPEAT_END_RE.sub(" ", sub_asides(text, lambda _: " "))))


def section_keys(text: str) -> set[str]:
    """The section keys the song's tags name, sung lines under them or not."""
    keys = set()
    for raw in split_lines(text):
        tag = section_tag(raw) if is_tag(raw) else None
        if tag is not None:
            keys.add(section_key(tag))
    return keys


def parse(text: str) -> list[Line]:
    lines: list[Line] = []
    section, key = "", "default"
    unit, index = 0, 0
    open_unit = tagged = False  # tagged: a tag line with no lyric line after it yet
    for number, raw in enumerate(split_lines(text), 1):
        stripped = raw.strip()
        if is_tag(raw):
            tag = section_tag(raw, keep=tagged)
            if tag is not None:
                section, key = tag.strip(), section_key(tag)
            if open_unit:
                unit += 1
            open_unit, index, tagged = False, 0, True
            continue
        if not stripped:
            if open_unit:
                unit += 1
            # a tag after a blank line opens its own section: [Instrumental], then
            # [Spoken Word] with words under it, is no style kept on the instrumental
            open_unit, index, tagged = False, 0, False
            continue
        if not tokenize(stripped) and not has_digits(stripped):
            continue  # only a backing vocal or punctuation; digits are a line to flag
        lines.append(Line(number, stripped, section, key, unit, index))
        open_unit, tagged = True, False
        index += 1
    return lines


def held_note(token: str, vowels: Collection[str]) -> bool:
    """Ооо, Аааа, Օօօ: one vowel letter written three times or more is one held note."""
    low = token.lower()
    return len(low) >= 3 and len(set(low)) == 1 and low[0] in vowels


def squeeze(token: str, run: re.Pattern[str]) -> tuple[str, list[tuple[int, int]]] | None:
    """Ջաաաան as Ջան, Дааа as Да: each run of a vowel written three times or more,
    kept once, with the span of the token each kept letter stands for (the last
    letter of the run holds the rest); None if the token has no run. run's first
    group is the letters written once: ու for ուուու."""
    runs = list(run.finditer(token))
    if not runs:
        return None
    spans: list[tuple[int, int]] = []
    last = 0
    for m in runs:
        spans += [(k, k + 1) for k in range(last, m.start())]
        unit = len(m.group(1))
        spans += [(m.start() + j, m.start() + j + 1) for j in range(unit - 1)]
        spans.append((m.start() + unit - 1, m.end()))
        last = m.end()
    spans += [(k, k + 1) for k in range(last, len(token))]
    return "".join(token[a] for a, _ in spans), spans


def unsqueeze(texts: list[str], token: str, spans: list[tuple[int, int]]) -> list[str]:
    """Syllable texts of a squeezed word written with the token's letters again
    (Ջաաաան, Սի-րուուում); a letter the word is sung with but not written, as an
    Armenian schwa, stays."""
    out, at = [], 0
    for text in texts:
        piece = ""
        for ch in text:
            if at < len(spans) and token[spans[at][0]].lower() == ch.lower():
                piece += token[spans[at][0] : spans[at][1]]
                at += 1
            else:
                piece += ch
        out.append(piece)
    return out


MARKS = str.maketrans("", "", "́՛՜՞")  # an acute, ՛ ՜ ՞


def same_words(text: str) -> str:
    """A line as its words alone, to tell a copy: a last chorus may end on ! or ։,
    mark a stress (Արի՛, замо́к) or spell вернется for вернётся."""
    plain = text.lower().replace("ё", "е").translate(MARKS)
    return " ".join(re.sub(r"[^\w\s]", " ", plain).split())


# Emoji, with the joiners and selectors that build one: 💔, 🔥, ❤️, 👩‍❤️‍👨. Nothing to sing.
EMOJI_RE = re.compile(
    "[\U0001f000-\U0001faff\u2600-\u27bf\u2b00-\u2bff]"
    "(?:[\ufe0f\U0001f3fb-\U0001f3ff]|\u200d[\U0001f000-\U0001faff\u2600-\u27bf])*"
)


def emoji(text: str) -> list[str]:
    return EMOJI_RE.findall(text)
