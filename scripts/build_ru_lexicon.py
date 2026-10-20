"""Build ashugh's Russian stress table from the OpenRussian dictionary dump.

The source is https://github.com/Badestrand/russian-dictionary (CC BY-SA 4.0):
nouns.csv, verbs.csv, adjectives.csv and others.csv, tab separated, with every
inflected form written with an apostrophe after the stressed vowel.

    uv run scripts/build_ru_lexicon.py path/to/russian-dictionary

writes src/ashugh/data/ru_stress.tsv: one form per line, sorted by UTF-8 bytes,
followed by a tab and the 1-based positions of its stressed vowels ("21" means
the form is stressed on the second vowel in one reading and the first in
another), a headword's own stress first: вода is вода́ the noun before во́да of
вод, so where a line leaves the stress open it takes the common one. Forms
with one vowel are left out unless they contain ё, because their stress
carries no information but their ё does.

It also writes src/ashugh/data/ru_yo.tsv: the one-vowel forms that exist only
with ё (ждёт, шёл, лёд), one per line, so that ждет written without its ё
reads as ждёт. A form whose е spelling is a word too (всё and все) is left out.
"""

from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

VOWELS = set("аеёиоуыэюя")
FILES = ("nouns.csv", "verbs.csv", "adjectives.csv", "others.csv")
NOT_FORMS = {
    "bare",
    "translations_en",
    "translations_de",
    "gender",
    "partner",
    "animate",
    "indeclinable",
    "sg_only",
    "pl_only",
    "aspect",
}
FORM_RE = re.compile(r"[а-яё'\-]+")
OUT = Path(__file__).resolve().parent.parent / "src" / "ashugh" / "data" / "ru_stress.tsv"
YO_OUT = OUT.with_name("ru_yo.tsv")


def stress_positions(form: str) -> tuple[str, set[int], int]:
    positions: set[int] = set()
    count = 0
    for i, ch in enumerate(form):
        if ch in VOWELS:
            count += 1
            if ch == "ё" or (i + 1 < len(form) and form[i + 1] == "'"):
                positions.add(count)
    return form.replace("'", ""), positions, count


def past_forms(infinitive: str) -> list[str]:
    """The past tense of a verb whose dump row lists none, stressed like its infinitive.

    Only -ть and -ться verbs with a vowel before the ending and a stress mark
    qualify; -сть, -сти and -чь verbs change their stem in the past.
    """
    if "'" not in infinitive and "ё" not in infinitive:
        return []
    if infinitive.endswith("ться"):
        stem, endings = infinitive[:-4], ("лся", "лась", "лось", "лись")
    elif infinitive.endswith("ть"):
        stem, endings = infinitive[:-2], ("л", "ла", "ло", "ли")
    else:
        return []
    if not stem.rstrip("'") or stem.rstrip("'")[-1] not in VOWELS:
        return []
    return [stem + e for e in endings]


def all_forms(source: Path) -> set[str]:
    """Every form the dump lists, without its stress marks."""
    csv.field_size_limit(sys.maxsize)
    out: set[str] = set()
    for name in FILES:
        with open(source / name, encoding="utf-8", newline="") as fh:
            rows = csv.reader(fh, delimiter="\t")
            header = next(rows)
            columns = [i for i, h in enumerate(header) if h not in NOT_FORMS]
            for row in rows:
                for variant in (
                    v for i in columns if i < len(row) for v in re.split(r"[,;/]", row[i])
                ):
                    form = variant.strip().lower().replace("\u0301", "").replace("'", "")
                    form = form.replace("*", "")
                    if form and FORM_RE.fullmatch(form):
                        out.add(form)
    return out


def yo_only(forms: set[str]) -> list[str]:
    """One-vowel forms with ё whose е spelling is no form of its own."""
    return sorted(
        (
            f
            for f in forms
            if "ё" in f and sum(ch in VOWELS for ch in f) == 1 and f.replace("ё", "е") not in forms
        ),
        key=lambda f: f.encode(),
    )


def build(source: Path) -> dict[str, list[int]]:
    """Each form's stressed vowels, a headword's own stress first: вода lists вода́
    (the noun) before во́да (of вод, waters), so a reading the line leaves open
    is the common one."""
    csv.field_size_limit(sys.maxsize)
    table: dict[str, set[int]] = defaultdict(set)
    headword: dict[str, set[int]] = defaultdict(set)
    for name in FILES:
        with open(source / name, encoding="utf-8", newline="") as fh:
            rows = csv.reader(fh, delimiter="\t")
            header = next(rows)
            columns = [i for i, h in enumerate(header) if h not in NOT_FORMS]
            past = header.index("past_m") if "past_m" in header else None
            accented = header.index("accented") if "accented" in header else None
            for row in rows:
                forms = [v for i in columns if i < len(row) for v in re.split(r"[,;/]", row[i])]
                if accented is not None and accented < len(row):
                    head = row[accented].strip().lower().replace("\u0301", "'")
                    if FORM_RE.fullmatch(head):
                        bare, positions, _ = stress_positions(head)
                        headword[bare] |= positions
                listed_past = "".join(row[past : past + 1]).strip() if past is not None else "?"
                if accented is not None and not listed_past:
                    forms += past_forms(row[accented].strip().lower())
                for variant in forms:
                    form = variant.strip().lower().replace("\u0301", "'").replace("*", "")
                    if not FORM_RE.fullmatch(form):
                        continue
                    bare, positions, count = stress_positions(form)
                    if not positions or (count < 2 and "ё" not in bare):
                        continue
                    table[bare] |= positions
    return {
        form: sorted(positions & headword[form]) + sorted(positions - headword[form])
        for form, positions in table.items()
    }


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    table = build(Path(sys.argv[1]))
    keys = sorted(table, key=lambda k: k.encode())
    with open(OUT, "w", encoding="utf-8", newline="\n") as out:
        for key in keys:
            out.write(f"{key}\t{''.join(str(p) for p in table[key])}\n")
    print(f"{len(keys)} forms -> {OUT}")
    yo = yo_only(all_forms(Path(sys.argv[1])))
    YO_OUT.write_text("".join(f + "\n" for f in yo), encoding="utf-8", newline="\n")
    print(f"{len(yo)} forms only with ё -> {YO_OUT}")


if __name__ == "__main__":
    main()
