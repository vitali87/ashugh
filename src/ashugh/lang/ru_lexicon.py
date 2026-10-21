"""The bundled Russian stress tables (src/ashugh/data/ru_stress.tsv and ru_derived.tsv).

Each line is a form, a tab, and the 1-based positions of its stressed vowels,
a headword's own stress first. ru_stress.tsv holds the forms OpenRussian lists;
ru_derived.tsv the regular forms it leaves out (comparatives, participles, the
declension of a lemma listed without one), read only where the first has none.
Built by scripts/build_ru_lexicon.py from OpenRussian (CC BY-SA 4.0).
"""

from __future__ import annotations

from itertools import product

from ..table import SortedTable


class StressTable(SortedTable):
    def __init__(self, data: bytes | None = None, derived: bytes | None = None) -> None:
        super().__init__("data/ru_stress.tsv", data)
        if data is None:
            self.derived: SortedTable | None = SortedTable("data/ru_derived.tsv", derived)
        else:
            self.derived = None if derived is None else SortedTable(None, derived)

    def stresses(self, form: str) -> tuple[int, ...] | None:
        """0-based stressed vowel indices of form, or None if it is not listed."""
        raw = self.get(form)
        if raw is None and self.derived is not None:
            raw = self.derived.get(form)
        return None if raw is None else tuple(int(d) - 1 for d in raw if d.isdigit())

    def verb_only(self, form: str) -> frozenset[int]:
        """0-based stresses of form that only a verb form has (полю́ beside по́лю)."""
        raw = self.get(form) or ""
        return frozenset(int(d) - 1 for d, m in zip(raw, raw[1:] + " ") if d.isdigit() and m == "v")

    def variants(self, form: str) -> list[tuple[str, tuple[int, ...]]]:
        """Listed spellings of form with ё restored in any of its е's, form included."""
        slots = [i for i, ch in enumerate(form) if ch == "е"][:4]
        out = []
        for choice in product((False, True), repeat=len(slots)):
            chars = list(form)
            for slot, yo in zip(slots, choice):
                if yo:
                    chars[slot] = "ё"
            spelling = "".join(chars)
            stress = self.stresses(spelling)
            if stress is not None:
                out.append((spelling, stress))
        return out


TABLE = StressTable()
