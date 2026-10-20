"""Armenian sung syllables: ashugh against a hand-checked gold list and espeak-ng.

    uv run eval/armenian.py [--out eval/out/armenian.json]

eval/data/hy_gold.tsv lists Eastern Armenian words with their sung syllables,
one rule of schwa epenthesis per word. The script reports how often ashugh's
syllabification and syllable count match, and, when espeak-ng is available
(uv run --with espeakng-loader --with phonemizer eval/armenian.py), how
often espeak-ng's syllable count does, with every disagreement listed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ashugh.lang import hy  # noqa: E402

GOLD = Path(__file__).resolve().parent / "data" / "hy_gold.tsv"
IPA_VOWELS = set("aeiouəɛɔɪʊæɐ")


def gold() -> list[tuple[str, str, str]]:
    rows = []
    for line in GOLD.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            word, sung, rule = line.split("\t")
            rows.append((word, sung, rule))
    return rows


def espeak():
    """A word -> IPA function backed by espeak-ng, or None if it is not installed."""
    try:
        import espeakng_loader
        from phonemizer import phonemize
        from phonemizer.backend.espeak.wrapper import EspeakWrapper
    except ImportError:
        return None
    EspeakWrapper.set_library(espeakng_loader.get_library_path())
    EspeakWrapper.set_data_path(espeakng_loader.get_data_path())
    return lambda word: phonemize(word, language="hy", backend="espeak", strip=True)


def ipa_syllables(ipa: str) -> int:
    """Vowel symbols, except ɪ or ʊ right after a vowel, which is the glide of a diphthong."""
    count, previous = 0, False
    for ch in ipa:
        vowel = ch in IPA_VOWELS
        if vowel and not (previous and ch in "ɪʊ"):
            count += 1
        previous = vowel
    return count


def evaluate() -> dict:
    rows = gold()
    speak = espeak()
    tally: dict[str, dict[str, float]] = {"ashugh": {"exact": 0, "count": 0}}
    if speak:
        tally["espeak"] = {"count": 0}
    disagreements: list[dict] = []
    for word, sung, rule in rows:
        w = hy.analyze_word(word)
        mine = w.sung().lower()
        want = sung.lower()
        n = want.count("-") + 1
        exact = mine == want
        right_count = w.size == n
        tally["ashugh"]["exact"] += exact
        tally["ashugh"]["count"] += right_count
        row = {"word": word, "gold": sung, "ashugh": mine, "rule": rule}
        if speak:
            ipa = speak(word)
            row["espeak"] = ipa
            row["espeak_syllables"] = ipa_syllables(ipa)
            tally["espeak"]["count"] += row["espeak_syllables"] == n
        if not exact or (speak and row["espeak_syllables"] != n):
            disagreements.append(row)
    rates = {
        system: {key: round(value / len(rows), 4) for key, value in counts.items()}
        for system, counts in tally.items()
    }
    return {"words": len(rows), **rates, "disagreements": disagreements}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    text = json.dumps(evaluate(), ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
