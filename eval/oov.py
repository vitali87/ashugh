"""How ashugh does on words its dictionaries lack, estimated on held-out words.

    python eval/oov.py [--out eval/out/oov.json]

Every tenth dictionary entry (by a hash of the word) is held out; the suffix
stress prior is learned from the rest, the way scripts/build_suffix_stress.py
learns it, and asked to stress the held-out words. For English the spelling
syllable counter is scored on the held-out words too. A "majority" baseline
always predicts the most common stress position counted from the end.
"""

from __future__ import annotations

import argparse
import json
import sys
import zlib
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import build_suffix_stress as builder  # noqa: E402

from ashugh.lang import en  # noqa: E402


def held_out(word: str) -> bool:
    return zlib.crc32(word.encode()) % 10 == 0


def predict(prior: dict[str, tuple[int, float]], word: str) -> int | None:
    for n in range(5, 1, -1):
        if len(word) > n and word[-n:] in prior:
            return prior[word[-n:]][0]
    return None


def stress_accuracy(words: list[tuple[str, int]]) -> dict:
    train = [w for w in words if not held_out(w[0])]
    test = [w for w in words if held_out(w[0])]
    prior = builder.table(train)
    majority = Counter(after for _, after in train).most_common(1)[0][0]
    hits = covered = base = 0
    for word, after in test:
        guess = predict(prior, word)
        if guess is not None:
            covered += 1
            hits += guess == after
        base += majority == after
    hits_or_base = hits + sum(1 for w, a in test if predict(prior, w) is None and a == majority)
    return {
        "test_words": len(test),
        "prior_coverage": round(covered / len(test), 4),
        "prior_accuracy_where_covered": round(hits / covered, 4) if covered else None,
        "prior_with_majority_fallback": round(hits_or_base / len(test), 4),
        "majority_baseline": round(base / len(test), 4),
    }


def english_syllables() -> dict:
    total = right = 0
    for line in (builder.DATA / "en_cmudict.tsv").read_text(encoding="utf-8").splitlines():
        word, _, variants = line.partition("\t")
        if not word.isalpha() or not held_out(word):
            continue
        counts = {sum(ch.isdigit() for ch in v) for v in variants.split("|")}
        total += 1
        right += en.guess_syllables(word) in counts
    return {"test_words": total, "spelling_count_accuracy": round(right / total, 4)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = {
        "ru_stress": stress_accuracy(builder.russian()),
        "en_stress": stress_accuracy(builder.english()),
        "en_syllables": english_syllables(),
    }
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
