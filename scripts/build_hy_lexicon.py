"""Build ashugh's Armenian word lists: stems that end in ս or դ, and compounds.

The source is WikiPron's scrape of Wiktionary's Eastern Armenian
pronunciations (https://github.com/CUNY-CL/wikipron, file
data/scrape/tsv/hye_armn_e_broad.tsv, CC BY-SA, see NOTICE.md):

    uv run scripts/build_hy_lexicon.py path/to/hye_armn_e_broad.tsv

A final ս (my) or դ (your) after a consonant is usually the possessive and
takes a schwa (սե-րըս, տու-նըդ), but in some stems it is the stem's own:
մարդ, ադամանդ, նորահարս. Every Wiktionary entry is a dictionary form, so an
entry ending that way, transcribed without the schwa, names such a stem.

writes src/ashugh/data/hy_lexical.tsv: one lowercase word per line, sorted by
UTF-8 bytes. A word with several pronunciations is listed only if none has
the schwa.

A compound keeps the schwa of its second root (մեղադրել is մե-ղա-դը-րել,
from դրել), which no rule of clusters predicts. Where every pronunciation of
an entry has a schwa between two consonants inside the word and ashugh's
rules do not, the word's beginning up to the second consonant (մեղադր) goes
into src/ashugh/data/hy_compound.tsv, unless it would break an entry the
rules already read right.

eval/wikipron.py rebuilds both lists without every tenth word (hold_out=True)
and scores ashugh on the words they left out.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ashugh.lang import hy  # noqa: E402

OUT = ROOT / "src" / "ashugh" / "data" / "hy_lexical.tsv"
COMPOUNDS = ROOT / "src" / "ashugh" / "data" / "hy_compound.tsv"
VOWELS = set("ɑaeiouəɛɔ")
HOLD_OUT = 10


def words(source: Path) -> dict[str, list[list[str]]]:
    """Each word with its pronunciations (phone lists), in the source's order."""
    table: dict[str, list[list[str]]] = {}
    for line in source.read_text(encoding="utf-8").splitlines():
        word, _, ipa = line.partition("\t")
        if word and ipa:
            table.setdefault(word, []).append(ipa.split())
    return table


def held_out(k: int) -> bool:
    """Whether the k-th word of the source (from 0) is kept for the evaluation."""
    return k % HOLD_OUT == 0


def stem_final(word: str, phones: list[str]) -> bool | None:
    """Whether word ends in consonant + ս/դ that Wiktionary reads without a
    schwa; None if it does not end that way or the phones do not line up."""
    if not all(hy.is_armenian(ch) for ch in word):
        return None
    segs = hy.segments(hy.normalize(word))
    if len(segs) < 3 or segs[-1].ph not in ("s", "d") or segs[-2].vowel or segs[-2].ph == "j":
        return None
    if len([p for p in phones if p != "ə"]) != len(segs):
        return None  # cannot line the transcription up with the letters
    return phones[-2] != "ə"


def build(source: Path, hold_out: bool = False) -> list[str]:
    out = set()
    for k, (word, variants) in enumerate(words(source).items()):
        if hold_out and held_out(k):
            continue
        readings = [r for r in (stem_final(word, p) for p in variants) if r is not None]
        if readings and all(readings):
            out.add(hy.normalize(word))
    return sorted(out, key=lambda w: w.encode("utf-8"))


def _schwas_before(segs: list, phones: list[str]) -> set[int] | None:
    """Indices of the segments Wiktionary puts a schwa before; None if the
    phones do not line up with the letters."""
    if len([p for p in phones if p != "ə"]) != len(segs):
        return None
    out, j = set(), 0
    for p in phones:
        if p == "ə":
            out.add(j)
        else:
            j += 1
    return out


def _rule_schwas(norm: str) -> set[int]:
    """Indices of the segments ashugh's rules put a schwa before."""
    syllables = hy.syllabify(hy.segments(norm), not hy.stem_final(norm))
    out, j = set(), 0
    for s in (s for syl in syllables for s in syl):
        if s.epenthetic:
            out.add(j)
        else:
            j += 1
    return out


def _counts(variants: list[list[str]]) -> set[int]:
    return {sum(1 for p in v if p[0] in VOWELS) for v in variants}


def _size(norm: str, keys: set[str] | frozenset[str]) -> int:
    segs = hy.segments(norm)
    found = (norm[:k] for k in range(hy.MIN_COMPOUND, len(norm) + 1) if norm[:k] in keys)
    for i in sorted({len(hy.segments(key)) - 1 for key in found}, reverse=True):
        segs.insert(i, hy._schwa())
    return len(hy.syllabify(segs, not hy.stem_final(norm)))


def compounds(source: Path, hold_out: bool = False) -> list[str]:
    table = {
        hy.normalize(word): variants
        for k, (word, variants) in enumerate(words(source).items())
        if not (hold_out and held_out(k)) and all(hy.is_armenian(ch) for ch in word)
    }
    found: set[str] = set()
    for norm, variants in table.items():
        segs = hy.segments(norm)
        vowels = [i for i, s in enumerate(segs) if s.vowel]
        sets = [s for s in (_schwas_before(segs, v) for v in variants) if s is not None]
        if not sets or not vowels:
            continue
        for j in sorted(set.intersection(*sets) - _rule_schwas(norm)):
            inside = vowels[0] < j <= vowels[-1]
            if inside and not segs[j - 1].vowel and not segs[j].vowel:
                key = next(
                    norm[:k] for k in range(1, len(norm) + 1) if len(hy.segments(norm[:k])) > j
                )
                if len(key) >= hy.MIN_COMPOUND:
                    found.add(key)
    keep = set()
    for key in found:  # no key may break an entry the rules read right
        if not any(
            norm.startswith(key)
            and _size(norm, frozenset()) in _counts(v)
            and _size(norm, {key}) not in _counts(v)
            for norm, v in table.items()
        ):
            keep.add(key)
    return sorted(keep, key=lambda w: w.encode("utf-8"))


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    stems = build(Path(argv[0]))
    OUT.write_text("".join(w + "\n" for w in stems), encoding="utf-8")
    print(f"{len(stems)} stems -> {OUT}", file=sys.stderr)
    keys = compounds(Path(argv[0]))
    COMPOUNDS.write_text("".join(k + "\n" for k in keys), encoding="utf-8")
    print(f"{len(keys)} compound beginnings -> {COMPOUNDS}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
