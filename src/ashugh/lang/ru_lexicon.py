"""The bundled Russian stress table (src/ashugh/data/ru_stress.tsv).

Each line is a form, a tab, and the 1-based positions of its stressed vowels.
Lines are sorted by UTF-8 bytes, so a lookup is a binary search over the raw
file; nothing is parsed up front. Built by scripts/build_ru_lexicon.py from
OpenRussian (CC BY-SA 4.0).
"""

from __future__ import annotations

from importlib import resources
from itertools import product


class StressTable:
    def __init__(self, data: bytes | None = None) -> None:
        self._buf = data

    @property
    def buf(self) -> bytes:
        if self._buf is None:
            self._buf = resources.files("ashugh").joinpath("data/ru_stress.tsv").read_bytes()
        return self._buf

    def get(self, form: str) -> tuple[int, ...] | None:
        """0-based stressed vowel indices of form, or None if it is not listed."""
        buf = self.buf
        key = form.encode()
        lo, hi = 0, len(buf)
        while lo < hi:
            mid = (lo + hi) // 2
            start = buf.rfind(b"\n", 0, mid) + 1
            tab = buf.find(b"\t", start)
            found = buf[start:tab]
            if found == key:
                end = buf.find(b"\n", tab)
                return tuple(int(d) - 1 for d in buf[tab + 1 : end].decode())
            if found < key:
                lo = buf.find(b"\n", tab) + 1
            else:
                hi = start
        return None

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
            stress = self.get(spelling)
            if stress is not None:
                out.append((spelling, stress))
        return out


TABLE = StressTable()
