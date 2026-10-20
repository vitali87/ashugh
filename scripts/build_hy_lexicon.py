"""Build ashugh's list of Armenian words whose final ս or դ belongs to the stem.

The source is WikiPron's scrape of Wiktionary's Eastern Armenian
pronunciations (https://github.com/CUNY-CL/wikipron, file
data/scrape/tsv/hye_armn_e_broad.tsv, CC BY-SA, see NOTICE.md):

    uv run scripts/build_hy_lexicon.py path/to/hye_armn_e_broad.tsv

A final ս (my) or դ (your) after a consonant is usually the possessive and
takes a schwa (սե-րըս, տու-նըդ), but in some stems it is the stem's own:
մարդ, ադամանդ, նորահարս. Every Wiktionary entry is a dictionary form, so an
entry ending that way, transcribed without the schwa, names such a stem.

writes src/ashugh/data/hy_lexical.tsv: one lowercase word per line, sorted by
UTF-8 bytes. eval/wikipron.py rebuilds the list without every tenth entry
(build(source, hold_out=True)) and scores ashugh on those it left out.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ashugh.lang import hy  # noqa: E402

OUT = ROOT / "src" / "ashugh" / "data" / "hy_lexical.tsv"
HOLD_OUT = 10


def entries(source: Path) -> list[tuple[str, list[str]]]:
    rows = []
    for line in source.read_text(encoding="utf-8").splitlines():
        word, _, ipa = line.partition("\t")
        if word and ipa:
            rows.append((word, ipa.split()))
    return rows


def stem_final(word: str, phones: list[str]) -> bool:
    """Whether word ends in consonant + ս/դ that Wiktionary reads without a schwa."""
    if not all(hy.is_armenian(ch) for ch in word):
        return False
    segs = hy.segments(hy.normalize(word))
    if len(segs) < 3 or segs[-1].ph not in ("s", "d") or segs[-2].vowel or segs[-2].ph == "j":
        return False
    if len([p for p in phones if p != "ə"]) != len(segs):
        return False  # cannot line the transcription up with the letters
    return phones[-2] != "ə"


def build(source: Path, hold_out: bool = False) -> list[str]:
    rows = entries(source)
    return sorted(
        {
            hy.normalize(word)
            for i, (word, phones) in enumerate(rows)
            if not (hold_out and i % HOLD_OUT == 0) and stem_final(word, phones)
        },
        key=lambda w: w.encode("utf-8"),
    )


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    words = build(Path(argv[0]))
    OUT.write_text("".join(w + "\n" for w in words), encoding="utf-8")
    print(f"{len(words)} words -> {OUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
