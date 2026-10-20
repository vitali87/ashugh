"""Build ashugh's Russian stress table from the OpenRussian dictionary dump.

The source is https://github.com/Badestrand/russian-dictionary (CC BY-SA 4.0):
nouns.csv, verbs.csv, adjectives.csv and others.csv, tab separated, with every
inflected form written with an apostrophe after the stressed vowel.

    python scripts/build_ru_lexicon.py path/to/russian-dictionary

writes src/ashugh/data/ru_stress.tsv: one form per line, sorted by UTF-8 bytes,
followed by a tab and the 1-based positions of its stressed vowels ("12" means
the form is stressed on the first vowel in one reading and the second in
another). Forms with one vowel are left out unless they contain ё, because
their stress carries no information but their ё does.
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


def stress_positions(form: str) -> tuple[str, set[int], int]:
    positions: set[int] = set()
    count = 0
    for i, ch in enumerate(form):
        if ch in VOWELS:
            count += 1
            if ch == "ё" or (i + 1 < len(form) and form[i + 1] == "'"):
                positions.add(count)
    return form.replace("'", ""), positions, count


def build(source: Path) -> dict[str, set[int]]:
    csv.field_size_limit(sys.maxsize)
    table: dict[str, set[int]] = defaultdict(set)
    for name in FILES:
        with open(source / name, encoding="utf-8", newline="") as fh:
            rows = csv.reader(fh, delimiter="\t")
            header = next(rows)
            columns = [i for i, h in enumerate(header) if h not in NOT_FORMS]
            for row in rows:
                for i in columns:
                    if i >= len(row):
                        continue
                    for variant in re.split(r"[,;/]", row[i]):
                        form = variant.strip().lower().replace("\u0301", "'").replace("*", "")
                        if not FORM_RE.fullmatch(form):
                            continue
                        bare, positions, count = stress_positions(form)
                        if not positions or (count < 2 and "ё" not in bare):
                            continue
                        table[bare] |= positions
    return table


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    table = build(Path(sys.argv[1]))
    keys = sorted(table, key=lambda k: k.encode())
    with open(OUT, "w", encoding="utf-8", newline="\n") as out:
        for key in keys:
            out.write(f"{key}\t{''.join(str(p) for p in sorted(table[key]))}\n")
    print(f"{len(keys)} forms -> {OUT}")


if __name__ == "__main__":
    main()
