"""Armenian sung syllables against Wiktionary, on entries ashugh never saw.

    uv run eval/wikipron.py [--out eval/out/wikipron.json] [--src PATH]

The data is WikiPron's scrape of Wiktionary's Eastern Armenian pronunciations
(hye_armn_e_broad.tsv, downloaded on first use). ashugh's list of stems
ending in ս or դ (scripts/build_hy_lexicon.py) comes from the same data, so
the list is rebuilt here without every tenth entry, and ashugh is scored on
those alone: its sung syllables against the vowels of Wiktionary's broad
transcription, schwas included. --src points at another checkout's src/ to
score an older analyzer.

Wiktionary is not a record of singing, so the disagreements are sorted by
kind: vowel letters it reads as a glide (միլիառ as mil-jar, where ashugh
sings mi-li-ar), and schwas at the start, inside or at the end of a word.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = (
    "https://raw.githubusercontent.com/CUNY-CL/wikipron/master/data/scrape/tsv/hye_armn_e_broad.tsv"
)
DATA = ROOT / "eval" / "data" / "hye_armn_e_broad.tsv"
HOLD_OUT = 10  # as in scripts/build_hy_lexicon.py
VOWELS = set("ɑaeiouəɛɔ")


def load(path: Path = DATA) -> list[tuple[str, list[str]]]:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {URL}", file=sys.stderr)
        urllib.request.urlretrieve(URL, path)
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        word, _, ipa = line.partition("\t")
        if word and ipa:
            rows.append((word, ipa.split()))
    return rows


def kind(word, phones: list[str]) -> str:
    """Where ashugh and Wiktionary part: glide, or a schwa at start, middle or end."""
    syllables = word.syllables
    full = sum(1 for s in syllables if not s.epenthetic)
    if full != sum(1 for p in phones if p[0] in VOWELS and p != "ə"):
        return "vowel letter or glide"
    first = next(i for i, p in enumerate(phones) if p[0] in VOWELS and p != "ə")
    last = max(i for i, p in enumerate(phones) if p[0] in VOWELS and p != "ə")
    theirs = [i for i, p in enumerate(phones) if p == "ə"]
    mine_start = sum(1 for s in syllables[: _first_full(syllables)] if s.epenthetic)
    mine_end = sum(1 for s in syllables[_last_full(syllables) + 1 :] if s.epenthetic)
    if mine_start != sum(1 for i in theirs if i < first):
        return "schwa at the start"
    if mine_end != sum(1 for i in theirs if i > last):
        return "schwa at the end"
    return "schwa inside"


def _first_full(syllables) -> int:
    return next(i for i, s in enumerate(syllables) if not s.epenthetic)


def _last_full(syllables) -> int:
    return max(i for i, s in enumerate(syllables) if not s.epenthetic)


def evaluate(rows: list[tuple[str, list[str]]], hy) -> dict:
    tally: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    examples: dict[str, list[str]] = {}
    for i, (word, phones) in enumerate(rows):
        if i % HOLD_OUT or not all(hy.is_armenian(ch) for ch in word):
            continue
        if not any(p[0] in VOWELS and p != "ə" for p in phones):
            continue  # an abbreviation spelled out letter by letter
        w = hy.analyze_word(word)
        want = sum(1 for p in phones if p[0] in VOWELS)
        tally["words"] += 1
        tally["schwa words"] += "ə" in phones
        if w.size == want:
            tally["agree"] += 1
            tally["schwa agree"] += "ə" in phones
            continue
        k = kind(w, phones)
        kinds[k] += 1
        examples.setdefault(k, []).append(f"{word} /{''.join(phones)}/ {w.sung()}")
    rng = random.Random(0)
    return {
        "held_out_words": tally["words"],
        "agree": round(tally["agree"] / tally["words"], 4),
        "words_with_a_schwa": tally["schwa words"],
        "agree_with_a_schwa": round(tally["schwa agree"] / tally["schwa words"], 4),
        "disagreements": dict(kinds.most_common()),
        "examples": {k: rng.sample(v, min(12, len(v))) for k, v in sorted(examples.items())},
    }


def hold_out_lexicon(hy) -> None:
    """Make hy use the stem list built without the held-out entries."""
    if not hasattr(hy, "lexical_endings"):
        return  # an analyzer from before the list
    path = ROOT / "scripts" / "build_hy_lexicon.py"
    spec = importlib.util.spec_from_file_location("build_hy_lexicon", path)
    assert spec and spec.loader
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    words = frozenset(builder.build(DATA, hold_out=True)) | hy.NOT_POSSESSIVE
    hy.lexical_endings = lambda: words


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path)
    parser.add_argument("--src", type=Path, default=ROOT / "src")
    args = parser.parse_args()
    sys.path.insert(0, str(args.src.resolve()))
    from ashugh.lang import hy

    rows = load()
    hold_out_lexicon(hy)
    text = json.dumps(evaluate(rows, hy), ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
