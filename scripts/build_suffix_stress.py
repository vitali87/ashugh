"""Learn stress-by-ending priors for words the dictionaries do not list.

    python scripts/build_suffix_stress.py

For every word ending (2 to 5 letters) shared by enough dictionary forms,
records how many vowels most often follow the stressed vowel. Russian comes
from src/ashugh/data/ru_stress.tsv, English from en_cmudict.tsv. Writes
ru_suffix.tsv and en_suffix.tsv next to them: ending, tab, vowels after the
stress, tab, the share of forms that agree.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "src" / "ashugh" / "data"
MIN_FORMS = 12
MIN_SHARE = 0.6
LENGTHS = range(2, 6)


def russian() -> list[tuple[str, int]]:
    vowels = set("аеёиоуыэюя")
    out = []
    for line in (DATA / "ru_stress.tsv").read_text(encoding="utf-8").splitlines():
        form, _, positions = line.partition("\t")
        n = sum(ch in vowels for ch in form)
        if len(positions) == 1 and n >= 2 and "-" not in form:
            out.append((form, n - int(positions)))
    return out


def english() -> list[tuple[str, int]]:
    out = []
    for line in (DATA / "en_cmudict.tsv").read_text(encoding="utf-8").splitlines():
        word, _, variants = line.partition("\t")
        if "|" in variants or not word.isalpha():
            continue
        digits = [ch for ch in variants if ch.isdigit()]
        if len(digits) >= 2 and digits.count("1") == 1:
            out.append((word, len(digits) - 1 - digits.index("1")))
    return out


def table(words: list[tuple[str, int]]) -> dict[str, tuple[int, float]]:
    counts: dict[str, Counter] = defaultdict(Counter)
    for word, after in words:
        for n in LENGTHS:
            if len(word) > n:
                counts[word[-n:]][after] += 1
    out = {}
    for ending, c in counts.items():
        total = sum(c.values())
        after, top = c.most_common(1)[0]
        if total >= MIN_FORMS and top / total >= MIN_SHARE:
            out[ending] = (after, top / total)
    return out


def write(name: str, entries: dict[str, tuple[int, float]]) -> None:
    keys = sorted(entries, key=lambda k: k.encode())
    with open(DATA / name, "w", encoding="utf-8", newline="\n") as fh:
        for k in keys:
            after, share = entries[k]
            fh.write(f"{k}\t{after}\t{share:.2f}\n")
    print(f"{len(keys)} endings -> {DATA / name}")


if __name__ == "__main__":
    write("ru_suffix.tsv", table(russian()))
    write("en_suffix.tsv", table(english()))
