"""The bundled Russian stress table (src/ashugh/data/ru_stress.tsv).

Each line is a form, a tab, and the 1-based positions of its stressed vowels.
Built by scripts/build_ru_lexicon.py from OpenRussian (CC BY-SA 4.0).
"""

from __future__ import annotations

from itertools import product

from ..table import SortedTable


class StressTable(SortedTable):
    def __init__(self, data: bytes | None = None) -> None:
        super().__init__("data/ru_stress.tsv", data)

    def stresses(self, form: str) -> tuple[int, ...] | None:
        """0-based stressed vowel indices of form, or None if it is not listed."""
        raw = self.get(form)
        return None if raw is None else tuple(int(d) - 1 for d in raw)

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
