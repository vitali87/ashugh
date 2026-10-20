"""Russian stress and rhyme accuracy on the RIFMA dataset.

RIFMA (Koziev 2025, MIT, https://github.com/Koziev/Rifma) holds 5,121 Russian
poems and stanzas with every stress marked by hand and a rhyme scheme.

    python eval/rifma.py [--limit N] [--out eval/out/rifma.json]

downloads the dataset into eval/data/ on first use and reports:

* stress: for polysyllabic words with a gold stress mark, how often ashugh's
  stress is the gold one, by where the stress came from (dictionary,
  ambiguity resolved by the meter, guessed), and for the dictionary's first
  reading alone (no meter), the baseline the meter improves on;
* rhyme: over pairs of lines in the same stanza, the precision and recall
  of "these two lines rhyme" against the gold scheme.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ashugh import lyrics, rhyme  # noqa: E402
from ashugh.lang import ru  # noqa: E402
from ashugh.scan import scan  # noqa: E402
from ashugh.spec import Spec  # noqa: E402

URL = "https://raw.githubusercontent.com/Koziev/Rifma/main/rifma_dataset.json"
DATA = Path(__file__).resolve().parent / "data" / "rifma_dataset.json"
MARKS = re.compile("[̀̂]")


def load(path: Path = DATA) -> list[dict]:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {URL}", file=sys.stderr)
        urllib.request.urlretrieve(URL, path)
    return json.loads(path.read_text(encoding="utf-8"))


def gold_stresses(markup_line: str) -> list[tuple[str, int | None]]:
    """(normalized word, gold stressed vowel index) for each token of a marked-up line."""
    out = []
    for token in lyrics.tokenize(MARKS.sub("", markup_line)):
        norm, stress = ru.read_marks(token)
        out.append((norm.replace("ё", "е"), stress if "́" in token else None))
    return out


def evaluate(samples: list[dict]) -> dict:
    stress = Counter()
    by_source = Counter()
    by_source_ok = Counter()
    pairs = Counter()
    for sample in samples:
        text = MARKS.sub("", sample["poem_text"]).replace("́", "")
        rep = scan(text, Spec(language="ru"), lang="ru")
        markup = [ln for ln in sample["accentuation_markup"].split("\n") if ln.strip()]
        plain = [ln for ln in text.split("\n") if ln.strip()]
        if len(markup) != len(plain):
            stress["skipped_poems"] += 1
            continue
        reports = {lr.line.number: lr for lr in rep.lines}
        numbers = sorted(reports)
        for k, number in enumerate(numbers):
            lr = reports[number]
            if k >= len(markup):
                break
            gold = gold_stresses(markup[k])
            if len(gold) != len(lr.line.words):
                stress["skipped_lines"] += 1
                continue
            for i, (w, (g_norm, g_stress)) in enumerate(zip(lr.line.words, gold)):
                if w.size < 2 or g_stress is None or w.norm.replace("ё", "е") != g_norm:
                    continue
                chosen = lr.fit.stresses.get(i)
                source = "guess" if w.guessed else ("meter" if w.ambiguous else "dictionary")
                if w.readings and w.readings[0].source in ("mark", "user"):
                    source = "mark"
                stress["words"] += 1
                by_source[source] += 1
                if chosen == g_stress:
                    stress["right"] += 1
                    by_source_ok[source] += 1
                if w.readings and w.readings[0].stress == g_stress:
                    stress["first_reading_right"] += 1
        _rhyme_pairs(rep, sample.get("rhyme_scheme"), pairs)
    return _summary(stress, by_source, by_source_ok, pairs, len(samples))


def _rhyme_pairs(rep, scheme: str | None, pairs: Counter) -> None:
    if not scheme:
        return
    letters = scheme.replace(" ", "")
    lines = rep.lines
    if len(letters) != len(lines):
        return
    for unit in rep.units:
        idx = [lines.index(lr) for lr in unit.lines]
        for a_pos, a in enumerate(idx):
            for b in idx[a_pos + 1 :]:
                gold = letters[a] != "-" and letters[a] == letters[b]
                s = rhyme.match(lines[a].tails, lines[b].tails)[0]
                ours = s >= rhyme.THRESHOLD["near"]
                pairs[("tp" if gold else "fp") if ours else ("fn" if gold else "tn")] += 1


def _summary(stress, by_source, by_source_ok, pairs, n) -> dict:
    words = stress["words"] or 1
    tp, fp, fn = pairs["tp"], pairs["fp"], pairs["fn"]
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "samples": n,
        "stress": {
            "words": stress["words"],
            "accuracy": round(stress["right"] / words, 4),
            "first_reading_accuracy": round(stress["first_reading_right"] / words, 4),
            "by_source": {
                s: {"words": c, "accuracy": round(by_source_ok[s] / c, 4)}
                for s, c in sorted(by_source.items())
            },
            "skipped_lines": stress["skipped_lines"],
            "skipped_poems": stress["skipped_poems"],
        },
        "rhyme_pairs": {
            "pairs": sum(pairs.values()),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--limit", type=int, help="only the first N samples")
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    samples = load(args.data)[: args.limit]
    result = evaluate(samples)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
