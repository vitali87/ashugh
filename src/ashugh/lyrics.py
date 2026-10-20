"""Reading a lyrics file: section tags, stanzas, lines, word tokens.

Lyrics follow the Suno conventions: a line like [Verse 1] or [Chorus] opens a
section, a blank line ends a stanza, and text in parentheses is a backing
vocal, so it is left out of the line's count.
"""

from __future__ import annotations

import re

from .model import Line

TAG_RE = re.compile(r"^\s*\[([^\]]*)\]\s*$")
PAREN_RE = re.compile(r"\([^)]*\)")
LINE_BREAK_RE = re.compile(r"(\r\n|\r|\n)")
WORD_RE = re.compile(r"[^\W\d_](?:[^\W\d_]|[\u0301\u055b\u055c\u055e]|[-'’](?=[^\W\d_]))*")
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


def section_key(tag: str) -> str:
    """[Verse 2] -> verse, [Pre-Chorus] -> pre-chorus, [Припев x2: тише] -> chorus."""
    name = tag.split(":")[0].lower()
    name = re.sub(r"\bx\s*\d+\b|\b\d+\s*x\b|\d+", " ", name)
    name = re.sub(r"[^\w\s-]", " ", name)
    name = re.sub(r"\s+", " ", name).strip() or "default"
    known = SECTION_NAMES.get(name)
    return known.lower() if known else name


def split_lines(text: str, keepends: bool = False) -> list[str]:
    """Lines as editors count them: only \\n, \\r\\n and \\r end a line, not U+2028."""
    parts = LINE_BREAK_RE.split(text)
    lines = [parts[i] + (parts[i + 1] if keepends else "") for i in range(0, len(parts) - 1, 2)]
    if parts[-1]:
        lines.append(parts[-1])
    return lines


def tokenize(text: str) -> list[str]:
    return WORD_RE.findall(PAREN_RE.sub(" ", text))


def token_spans(text: str) -> list[tuple[int, int, str]]:
    """(start, end, token) of every word outside parentheses, as tokenize sees them."""
    masked = PAREN_RE.sub(lambda m: " " * len(m.group(0)), text)
    return [(m.start(), m.end(), m.group(0)) for m in WORD_RE.finditer(masked)]


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
        if not tokenize(stripped):  # only a backing vocal or punctuation
            continue
        lines.append(Line(number, stripped, section, key, unit, index))
        open_unit = True
        index += 1
    return lines
