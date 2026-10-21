"""Reading a lyrics file: section tags, stanzas, lines, word tokens.

Lyrics follow the Suno conventions: a line like [Verse 1] or [Chorus] opens a
section, a blank line ends a stanza, and text in parentheses is a backing
vocal, so it is left out of the line's count.
"""

from __future__ import annotations

import re

from .model import Line

TAG_RE = re.compile(r"^\ufeff?\s*\[([^\]]*)\]\s*$")  # a BOM may open the file
PAREN_RE = re.compile(r"\([^)]*\)")
LINE_BREAK_RE = re.compile(r"(\r\n|\r|\n)")
WORD_RE = re.compile(
    r"(?<![^\W_])(?>[^\W\d_](?:[^\W\d_]|[\u0301\u055b\u055c\u055e]|[-'’](?=[^\W\d_]))*"
    r"(?:(?<=[iI][nN])['’](?![^\W\d_]))?)(?!\d)"  # a dropped g: goin', lovin'
    r"|&"  # sung as and, и, և
)  # letters glued to digits ('80s, 4ever, mp3) are no word: the digits warn
DIGIT_RE = re.compile(r"\d")


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
    "solo": "Solo",
    "соло": "Solo",
}


# Ordinals in section tags, in English, Russian and Armenian: a number (Второй куплет
# is Verse 2) or the last section (Финальный припев, Վերջին կրկներգ: Final Chorus).
ORDINALS = (
    (r"first|перв\w*|առաջին", "1"),
    (r"second|втор\w*|երկրորդ", "2"),
    (r"third|трет\w*|երրորդ", "3"),
    (r"fourth|четв[её]рт\w*|չորրորդ", "4"),
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


def section_key(tag: str) -> str:
    """[Verse 2] -> verse, [Pre-Chorus] -> pre-chorus, [Припев x2: тише] -> chorus."""
    name = re.sub(r"\([^)]*\)", " ", tag.split(":")[0].lower())  # (Female), (x2)
    name = ORDINAL_RE.sub(" ", name)
    name = re.sub(r"(?<!\w)[xх×]\s*\d+\b|\b\d+\s*[xх×](?!\w)|\d+", " ", name)
    name = re.sub(r"[^\w\s-]", " ", name)
    name = re.sub(r"\s+", " ", name).strip() or "default"
    known = SECTION_NAMES.get(name)
    return known.lower() if known else name


def suno_tag(tag: str) -> str | None:
    """A tag's text as Suno names the section: Финальный припев -> Final Chorus,
    Куплет 1 (тихо) -> Verse 1 (тихо), Կրկներգ (x2) -> Chorus x2; None for a
    section Suno has no name for."""
    head, colon, rest = tag.partition(":")
    notes: list[str] = []
    repeat = ""

    def aside(m: re.Match) -> str:
        nonlocal repeat
        r = REPEAT_RE.fullmatch(m.group(1).strip())
        if r:
            repeat = _repeat(r)
        else:
            notes.append(m.group(0))
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
    known = SECTION_NAMES.get(name)
    if known is None:
        return None
    parts = ["Final"] if "Final" in ordinals else []
    parts += [known, *numbers[:1], *([repeat] if repeat else []), *notes]
    return " ".join(parts) + colon + rest.rstrip()


def retag(line: str) -> str:
    """A tag line with its section named as Suno names it; any other line as it is."""
    body = line.rstrip("\r\n")
    m = TAG_RE.match(body)
    named = suno_tag(m.group(1)) if m else None
    if named is None:
        return line
    lead = body[: len(body) - len(body.lstrip())]
    return f"{lead}[{named}]" + line[len(body) :]


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


def token_spans(text: str) -> list[tuple[int, int, str]]:
    """(start, end, token) of every word outside parentheses, as tokenize sees them."""
    masked = PAREN_RE.sub(lambda m: " " * len(m.group(0)), text)
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


def has_digits(text: str) -> bool:
    return bool(DIGIT_RE.search(PAREN_RE.sub(" ", text)))


def parse(text: str) -> list[Line]:
    lines: list[Line] = []
    section, key = "", "default"
    unit, index = 0, 0
    open_unit = False
    for number, raw in enumerate(split_lines(text), 1):
        stripped = raw.strip()
        tag = TAG_RE.match(raw)
        if tag:
            section, key = tag.group(1).strip(), section_key(tag.group(1))
            if open_unit:
                unit += 1
            open_unit, index = False, 0
            continue
        if not stripped:
            if open_unit:
                unit += 1
            open_unit, index = False, 0
            continue
        if not tokenize(stripped) and not has_digits(stripped):
            continue  # only a backing vocal or punctuation; digits are a line to flag
        lines.append(Line(number, stripped, section, key, unit, index))
        open_unit = True
        index += 1
    return lines
