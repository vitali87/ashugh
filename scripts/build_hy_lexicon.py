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

A compound also keeps the schwa of a second root that opens on two
consonants, as the root does alone (լուսանշան is լու-սա-նը-շան, from նշան).
Every entry that opens that way, with a schwa between its first two
consonants in all its pronunciations, goes into src/ashugh/data/hy_roots.tsv,
unless after a linker ա or ե it would break an entry the rules read right
(կցել would make համագործակցել հա-մա-գոր-ծա-կը-ցել). A root that opens on ս,
զ or շ and a stop is left out: its schwa comes before it, and a linker's
vowel swallows that one.

A short word written in capitals for emphasis (ՔԵԶ, ԴՈՒ, ԻՆՁ) looks like an
abbreviation, which is sung letter by letter (ԱՄՆ, ԵՊՀ). Every entry of two to
five letters not itself in capitals goes into src/ashugh/data/hy_short.tsv, so
such a word stays a word; the abbreviations Wiktionary lists are in capitals.

eval/wikipron.py rebuilds the lists without every tenth word (hold_out=True)
and scores ashugh on the words they left out.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ashugh.lang import hy  # noqa: E402
from ashugh.phon import is_stop  # noqa: E402

OUT = ROOT / "src" / "ashugh" / "data" / "hy_lexical.tsv"
COMPOUNDS = ROOT / "src" / "ashugh" / "data" / "hy_compound.tsv"
ROOTS = ROOT / "src" / "ashugh" / "data" / "hy_roots.tsv"
SHORT = ROOT / "src" / "ashugh" / "data" / "hy_short.tsv"
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


def _size(
    norm: str, keys: set[str] | frozenset[str], roots: set[str] | frozenset[str] = frozenset()
) -> int:
    segs = hy.segments(norm)
    found = (norm[:k] for k in range(hy.MIN_COMPOUND, len(norm) + 1) if norm[:k] in keys)
    points = {len(hy.segments(key)) - 1 for key in found} | set(hy.root_points(norm, roots))
    for i in sorted(points, reverse=True):
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


def roots(source: Path, keys: frozenset[str], hold_out: bool = False) -> list[str]:
    """Entries that open on two consonants split by a schwa (նշան), less those
    that would break an entry the rules and the compound keys read right."""
    table = {
        hy.normalize(word): variants
        for k, (word, variants) in enumerate(words(source).items())
        if not (hold_out and held_out(k)) and all(hy.is_armenian(ch) for ch in word)
    }
    found = set()
    for norm, variants in table.items():
        segs = hy.segments(norm)
        if len(norm) < hy.MIN_ROOT or len(segs) < 3 or any(s.vowel for s in segs[:2]):
            continue
        if segs[1].ph == "j" or (segs[0].ph in hy.PROTHESIS_FIRST and is_stop(segs[1].ph)):
            continue  # կյանք opens on one onset; ստ- takes its schwa in front
        if all(len(v) > 1 and v[1] == "ə" for v in variants):
            found.add(norm)
    broken = set()
    for norm, v in table.items():
        hits = {r for r in _roots_in(norm, found)}
        if hits and _size(norm, keys) in _counts(v):
            broken |= {r for r in hits if _size(norm, keys, {r}) not in _counts(v)}
    return sorted(found - broken, key=lambda w: w.encode("utf-8"))


def _roots_in(norm: str, roots: set[str]) -> set[str]:
    """The roots that open after a linker in norm."""
    return {
        norm[k:j]
        for k in range(hy.MIN_HEAD, len(norm) - hy.MIN_ROOT + 1)
        if norm[k - 1] in hy.LINKERS
        for j in range(k + hy.MIN_ROOT, len(norm) + 1)
        if norm[k:j] in roots
    }


def short_words(source: Path) -> list[str]:
    """The entries of two to five letters, lowercase, abbreviations left out."""
    found = {
        w.lower() for w in words(source) if 2 <= len(w) <= 5 and w.isalpha() and not w.isupper()
    }
    return sorted(found, key=lambda w: w.encode())


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
    found = roots(Path(argv[0]), frozenset(keys))
    ROOTS.write_text("".join(r + "\n" for r in found), encoding="utf-8")
    print(f"{len(found)} roots that open on a cluster -> {ROOTS}", file=sys.stderr)
    short = short_words(Path(argv[0]))
    SHORT.write_text("".join(w + "\n" for w in short), encoding="utf-8")
    print(f"{len(short)} short words -> {SHORT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
