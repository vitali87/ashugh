"""Armenian sung syllables against Wiktionary, on entries ashugh never saw.

    uv run eval/wikipron.py [--out eval/out/wikipron.json] [--src PATH]

The data is WikiPron's scrape of Wiktionary's Eastern Armenian pronunciations
(hye_armn_e_broad.tsv, downloaded on first use). ashugh's list of stems
ending in ս or դ (scripts/build_hy_lexicon.py) comes from the same data, so
the list is rebuilt here without every tenth word, and ashugh is scored on
those alone: its sung syllables against the vowels of Wiktionary's broad
transcription, schwas included. A word that Wiktionary transcribes more than
one way (կերակրել with and without the schwa of its second root) matches
when ashugh agrees with any of them, and a word whose schwa ashugh makes
optional matches at either length. --src points at another checkout's src/
to score an older analyzer.

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
VOWELS = set("ɑaeiouəɛɔ")


def download(path: Path = DATA) -> Path:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {URL}", file=sys.stderr)
        urllib.request.urlretrieve(URL, path)
    return path


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


def evaluate(table: dict[str, list[list[str]]], hy, builder) -> dict:
    tally: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    examples: dict[str, list[str]] = {}
    for k, (word, variants) in enumerate(table.items()):
        if not builder.held_out(k) or not all(hy.is_armenian(ch) for ch in word):
            continue
        phones = variants[0]
        if not any(p[0] in VOWELS and p != "ə" for p in phones):
            continue  # an abbreviation spelled out letter by letter
        w = hy.analyze_word(word)
        counts = {sum(1 for p in v if p[0] in VOWELS) for v in variants}
        tally["words"] += 1
        tally["schwa words"] += "ə" in phones
        sizes = {w.size} | ({w.size - 1} if getattr(w, "optional", None) is not None else set())
        if sizes & counts:  # an optional schwa: ashugh accepts both lengths
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


def load_builder():
    path = ROOT / "scripts" / "build_hy_lexicon.py"
    spec = importlib.util.spec_from_file_location("build_hy_lexicon", path)
    assert spec and spec.loader
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    return builder


def hold_out_lexicon(hy, builder) -> None:
    """Make hy use word lists built without the held-out words."""
    if hasattr(hy, "lexical_endings"):
        words = frozenset(builder.build(DATA, hold_out=True)) | hy.NOT_POSSESSIVE
        hy.lexical_endings = lambda: words
    if hasattr(hy, "compound_schwas"):
        keys = frozenset(builder.compounds(DATA, hold_out=True))
        hy.compound_schwas = lambda: keys


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path)
    parser.add_argument("--src", type=Path, default=ROOT / "src")
    args = parser.parse_args()
    sys.path.insert(0, str(args.src.resolve()))
    from ashugh.lang import hy

    builder = load_builder()
    table = builder.words(download())
    hold_out_lexicon(hy, builder)
    text = json.dumps(evaluate(table, hy, builder), ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
