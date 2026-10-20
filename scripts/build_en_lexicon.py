"""Build ashugh's English pronunciation table from CMUdict.

The source is https://github.com/cmusphinx/cmudict (cmudict.dict, BSD-style
license, see NOTICE.md).

    uv run scripts/build_en_lexicon.py path/to/cmudict.dict

writes src/ashugh/data/en_cmudict.tsv: one lowercase word per line, sorted by
UTF-8 bytes, a tab, then its pronunciations in ARPABET with stress digits,
separated by "|".
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "src" / "ashugh" / "data" / "en_cmudict.tsv"
WORD_RE = re.compile(r"[a-z][a-z'.\-]*")


def build(source: Path) -> dict[str, list[str]]:
    table: dict[str, list[str]] = defaultdict(list)
    for raw in source.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        head, _, phones = line.partition(" ")
        word = re.sub(r"\(\d+\)$", "", head).lower()
        phones = " ".join(phones.split())
        if WORD_RE.fullmatch(word) and phones and phones not in table[word]:
            table[word].append(phones)
    return table


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    table = build(Path(sys.argv[1]))
    keys = sorted(table, key=lambda k: k.encode())
    with open(OUT, "w", encoding="utf-8", newline="\n") as out:
        for key in keys:
            out.write(f"{key}\t{'|'.join(table[key])}\n")
    print(f"{len(keys)} words -> {OUT}")


if __name__ == "__main__":
    main()
