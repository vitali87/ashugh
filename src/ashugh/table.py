"""Sorted tab-separated tables bundled in ashugh/data, read by binary search.

Each line is a key, a tab and a value; lines are sorted by the UTF-8 bytes of
the key. Nothing is parsed up front, so a lookup costs a few dozen probes into
the raw bytes whatever the table's size.
"""

from __future__ import annotations

from importlib import resources


class SortedTable:
    def __init__(self, resource: str | None = None, data: bytes | None = None) -> None:
        self._resource = resource
        self._buf = data

    @property
    def buf(self) -> bytes:
        if self._buf is None:
            if self._resource is None:
                raise ValueError("SortedTable needs a resource name or data")
            self._buf = resources.files("ashugh").joinpath(self._resource).read_bytes()
        return self._buf

    def get(self, key: str) -> str | None:
        if not key or "\n" in key or "\t" in key:
            return None
        buf = self.buf
        target = key.encode()
        lo, hi = 0, len(buf)
        while lo < hi:
            mid = (lo + hi) // 2
            start = buf.rfind(b"\n", 0, mid) + 1
            tab = buf.find(b"\t", start)
            found = buf[start:tab]
            if found == target:
                end = buf.find(b"\n", tab)
                return buf[tab + 1 : end if end >= 0 else len(buf)].decode()
            if found < target:
                nxt = buf.find(b"\n", tab)
                if nxt < 0:
                    break
                lo = nxt + 1
            else:
                hi = start
        return None
