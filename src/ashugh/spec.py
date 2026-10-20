"""Song specs: what each section of a song must satisfy.

A spec is a TOML file. Keys at the top level apply to every section; a
[section.<name>] table overrides them for sections whose tag normalizes to
<name> ([Verse 1] and [Verse 2] are both "verse"; untagged stanzas are
"default"). Lists cycle over a stanza's lines, so syllables = [8, 6] means
8, 6, 8, 6, ...

    language = "hy"              # hy | ru | en; detected per line when omitted
    syllables = 8                # or [8, 8, 8, 6]
    tolerance = 0                # allowed miss in syllables
    meter = "iamb4"              # iamb trochee dactyl amphibrach anapest dolnik free,
                                 # optionally followed by the number of feet
    rhyme = "ABAB"               # "-" or "." marks a line that need not rhyme; mixed case
                                 # (AbAb) also asks for feminine/masculine endings
    endings = "fmfm"             # m masculine, f feminine, d dactylic, - any
    min_rhyme = "near"           # perfect | near | slant | assonance
    forbid_final = ["ը"]         # a line may not end in these letters

    [section.chorus]
    syllables = [7, 7, 7, 5]
    rhyme = "AABB"

    [lexicon]                    # fixes for words the analyzer gets wrong
    "սկսել" = "ըս-կը-սել"        # Armenian: sung syllables, hidden ը written out
    "замок" = "замо́к"            # Russian: stress mark (acute, capital vowel or ё)
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path

from . import lyrics
from .lang import ANALYZERS
from .meter import parse_meter
from .rhyme import THRESHOLD

RULE_KEYS = {
    "syllables",
    "tolerance",
    "meter",
    "feet",
    "rhyme",
    "endings",
    "min_rhyme",
    "forbid_final",
}
TOP_KEYS = RULE_KEYS | {"language", "section", "stanza", "lexicon"}
ENDING_CODES = {"m": 0, "f": 1, "d": 2, "h": 3}


class SpecError(ValueError):
    pass


@dataclass(frozen=True)
class Rule:
    syllables: tuple[int, ...] = ()
    tolerance: int = 0
    meter: str | None = None
    feet: tuple[int, ...] = ()
    rhyme: str | None = None
    rhyme_parts: tuple[str, ...] = ()  # "ABBA ABBA": the scheme of each stanza, in turn
    endings: str | None = None
    min_rhyme: str = "near"
    forbid_final: tuple[str, ...] = ()

    @property
    def empty(self) -> bool:
        return self == Rule()

    def syllables_at(self, i: int) -> int | None:
        return self.syllables[i % len(self.syllables)] if self.syllables else None

    def feet_at(self, i: int) -> int | None:
        return self.feet[i % len(self.feet)] if self.feet else None

    def ending_at(self, i: int) -> int | None:
        if self.endings:
            code = self.endings[i % len(self.endings)].lower()
            return ENDING_CODES.get(code)
        if self.rhyme and mixed_case(self.rhyme):
            ch = self.rhyme[i % len(self.rhyme)]
            if ch.isalpha():
                return 1 if ch.isupper() else 0
        return None

    def rhyme_at(self, i: int) -> str | None:
        """Group label of line i; repeats of the scheme get fresh groups."""
        if not self.rhyme:
            return None
        n = len(self.rhyme)
        ch = self.rhyme[i % n]
        if not ch.isalpha():
            return None
        return f"{ch.upper()}{i // n}"


@dataclass
class Spec:
    path: str | None = None
    language: str | None = None
    base: Rule = field(default_factory=Rule)
    sections: dict[str, Rule] = field(default_factory=dict)
    lexicon: dict[str, str] = field(default_factory=dict)
    stanzas: dict[int, Rule] = field(default_factory=dict)  # 1-based stanza number

    def rule_for(self, key: str, unit: int | None = None) -> Rule:
        """The rule of a stanza: its own [stanza.N] table, else its section's, else the top."""
        if unit is not None and unit + 1 in self.stanzas:
            return self.stanzas[unit + 1]
        return self.sections.get(key, self.base)

    @property
    def empty(self) -> bool:
        return self.base.empty and not self.sections and not self.stanzas


def mixed_case(s: str) -> bool:
    letters = [c for c in s if c.isalpha()]
    return any(c.isupper() for c in letters) and any(c.islower() for c in letters)


def _int_list(name: str, value, where: str) -> tuple[int, ...]:
    if isinstance(value, bool):
        raise SpecError(f"{where}: {name} must be a number or a list of numbers")
    if isinstance(value, int):
        return (value,)
    if isinstance(value, str):
        parts = [p for p in value.replace(",", " ").split() if p]
        if parts and all(p.isdigit() for p in parts):
            return tuple(int(p) for p in parts)
    if (
        isinstance(value, list)
        and value
        and all(isinstance(v, int) and not isinstance(v, bool) for v in value)
    ):
        return tuple(value)
    raise SpecError(f"{where}: {name} must be a number or a list of numbers, got {value!r}")


def apply(table: dict, base: Rule, where: str) -> Rule:
    """base with the rule keys in table applied on top."""
    unknown = set(table) - RULE_KEYS
    if unknown:
        raise SpecError(f"{where}: unknown key(s) {', '.join(sorted(unknown))}")
    changes: dict = {}
    if "syllables" in table:
        changes["syllables"] = _int_list("syllables", table["syllables"], where)
    if "tolerance" in table:
        tol = table["tolerance"]
        if not isinstance(tol, int) or isinstance(tol, bool) or tol < 0:
            raise SpecError(f"{where}: tolerance must be a whole number >= 0")
        changes["tolerance"] = tol
    if "meter" in table:
        try:
            name, feet = parse_meter(str(table["meter"]))
        except ValueError as e:
            raise SpecError(f"{where}: {e}") from None
        changes["meter"] = name
        if feet is not None:
            changes["feet"] = (feet,)
    if "feet" in table:
        changes["feet"] = _int_list("feet", table["feet"], where)
    if "rhyme" in table:
        parts = str(table["rhyme"]).split()
        r = "".join(parts)
        if not r or not all(c.isalpha() or c in "-.*" for c in r):
            raise SpecError(
                f"{where}: rhyme must be letters like ABAB, with - or . for a free line"
            )
        changes["rhyme"] = r
        changes["rhyme_parts"] = tuple(parts) if len(parts) > 1 else ()
    if "endings" in table:
        e = str(table["endings"]).replace(" ", "").lower()
        if not e or not all(c in "mfdh-" for c in e):
            raise SpecError(f"{where}: endings must use m, f, d, h or - (e.g. fmfm)")
        changes["endings"] = e
    if "min_rhyme" in table:
        m = str(table["min_rhyme"])
        if m not in THRESHOLD or m == "none":
            raise SpecError(f"{where}: min_rhyme must be perfect, near, slant or assonance")
        changes["min_rhyme"] = m
    if "forbid_final" in table:
        ff = table["forbid_final"]
        ff = [ff] if isinstance(ff, str) else ff
        if not isinstance(ff, list) or not all(isinstance(x, str) and x for x in ff):
            raise SpecError(f"{where}: forbid_final must be a list of strings")
        changes["forbid_final"] = tuple(x.lower() for x in ff)
    return replace(base, **changes)


def from_dict(data: dict, path: str | None = None) -> Spec:
    where = path or "spec"
    unknown = set(data) - TOP_KEYS
    if unknown:
        raise SpecError(f"{where}: unknown key(s) {', '.join(sorted(unknown))}")
    language = data.get("language")
    if language is not None and language not in ANALYZERS:
        raise SpecError(f"{where}: language must be one of {', '.join(sorted(ANALYZERS))}")
    base = apply({k: v for k, v in data.items() if k in RULE_KEYS}, Rule(), where)
    sections = {}
    raw_sections = data.get("section", {})
    if not isinstance(raw_sections, dict):
        raise SpecError(f"{where}: [section.<name>] tables expected")
    for name, table in raw_sections.items():
        if not isinstance(table, dict):
            raise SpecError(f"{where}: section.{name} must be a table")
        key = lyrics.section_key(name)
        if key in sections:
            raise SpecError(f"{where}: section.{name} and another table name the same section")
        sections[key] = apply(table, base, f"{where} [section.{name}]")
    stanzas = {}
    raw_stanzas = data.get("stanza", {})
    if not isinstance(raw_stanzas, dict):
        raise SpecError(f"{where}: [stanza.<number>] tables expected")
    for name, table in raw_stanzas.items():
        if not str(name).isdigit() or int(name) < 1 or not isinstance(table, dict):
            raise SpecError(f"{where}: stanza.{name} must be a table numbered from 1")
        stanzas[int(name)] = apply(table, base, f"{where} [stanza.{name}]")
    lexicon = data.get("lexicon", {})
    if not isinstance(lexicon, dict) or not all(isinstance(v, str) for v in lexicon.values()):
        raise SpecError(f"{where}: [lexicon] maps words to strings")
    lexicon = {k.lower(): v for k, v in lexicon.items()}
    return Spec(path, language, base, sections, lexicon, stanzas)


def load(path: str | Path) -> Spec:
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as e:
        raise SpecError(f"{path}: {e}") from None
    return from_dict(data, str(path))


def loads(text: str, path: str | None = None) -> Spec:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise SpecError(f"{path or 'spec'}: {e}") from None
    return from_dict(data, path)


def _toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    raise TypeError(f"cannot write {value!r} to a spec")


def dumps(data: dict) -> str:
    """A spec dict (as from_dict takes it) written as TOML."""
    out = [f"{k} = {_toml_value(v)}" for k, v in data.items() if not isinstance(v, dict)]
    for table in ("section", "stanza", "lexicon"):
        entries = data.get(table) or {}
        if table == "lexicon" and entries:
            out += ["", "[lexicon]"] + [
                f"{_toml_value(k)} = {_toml_value(v)}" for k, v in entries.items()
            ]
            continue
        for name, rules in entries.items():
            out += ["", f"[{table}.{name}]"] + [f"{k} = {_toml_value(v)}" for k, v in rules.items()]
    return "\n".join(out) + "\n"


TEMPLATE = """\
# ashugh song spec. Top-level keys apply to every section; [section.<tag>]
# overrides them for [Verse 1], [Verse 2] (-> verse), [Chorus] (-> chorus) ...
language = "{lang}"
tolerance = 0
min_rhyme = "near"
{forbid}
[section.verse]
syllables = 8
meter = "iamb4"
rhyme = "ABAB"

[section.chorus]
syllables = [7, 7, 7, 5]
rhyme = "AABB"

[lexicon]
# word = how it is sung
{lexicon}
"""


def template(lang: str = "hy") -> str:
    if lang == "ru":
        return TEMPLATE.format(lang="ru", forbid="", lexicon='# "замок" = "замо́к"')
    return TEMPLATE.format(
        lang="hy", forbid='forbid_final = ["ը"]\n', lexicon='# "սկսել" = "ըս-կը-սել"'
    )
