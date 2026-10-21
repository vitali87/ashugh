"""A language server: lines that do not scan get underlined in the editor.

    ashugh lsp

speaks the Language Server Protocol over stdio. On every open and change it
scans the document and publishes the issues as diagnostics on their lines;
hovering a line shows how it is sung. The spec is found next to the file:
<name>.toml for <name>.txt, else the nearest ashugh.toml in this or a
parent folder; without one the server reports only warnings and notes.
"""

from __future__ import annotations

import io
import json
import re
import select
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

from . import lyrics
from .model import ACUTE
from .scan import DIGITS, Report, scan
from .spec import Spec, SpecError, load

SEVERITY = {"error": 1, "warning": 2, "info": 3}


class FramingError(ValueError):
    """A message that cannot be read; the next Content-Length starts afresh."""


EOF_ = object()  # the end of the stream, which a JSON null body is not


def read_message(stream):
    """One Content-Length framed JSON message, or EOF_ at the end of the stream.

    A frame with a bad or missing length raises FramingError; its body is then
    skipped up to the next Content-Length header, so one bad frame cannot put
    the rest out of step."""
    length = None
    while True:
        line = stream.readline()
        if not line:
            return EOF_
        at = line.lower().find(b"content-length:")
        if at > 0:  # the unread body of a bad frame, then the next header
            line = line[at:]
        line = line.strip()
        if not line:
            if length is None:
                raise FramingError("message without Content-Length")
            break
        name, _, value = line.decode("ascii", "replace").partition(":")
        if name.strip().lower() == "content-length":
            value = value.strip()
            if not (value.isascii() and value.isdigit()) or len(value) > 9:  # under 1 GB
                raise FramingError(f"bad Content-Length: {value!r}")
            length = int(value)
    body = stream.read(length)
    if len(body) < length:
        return EOF_
    return json.loads(body.decode("utf-8", "replace"))


def write_message(stream, msg: dict) -> None:
    body = json.dumps(msg).encode("ascii")  # escaped: a lone surrogate cannot break it
    stream.write(b"Content-Length: %d\r\n\r\n" % len(body) + body)
    stream.flush()


def path_of(uri: str) -> Path | None:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    return Path(unquote(parsed.path))


def find_spec(path: Path) -> Path | None:
    sibling = path.with_suffix(".toml")
    if sibling.exists() and sibling != path:
        return sibling
    for folder in [path.parent, *path.parent.parents]:
        candidate = folder / "ashugh.toml"
        if candidate.exists():
            return candidate
    return None


class BadParams(ValueError):
    pass


class Server:
    def __init__(self) -> None:
        self.docs: dict[str, str] = {}
        self.reports: dict[str, tuple[str, tuple[Report | None, str | None]]] = {}
        self.done = False
        self.shutdown = False

    def handle(self, msg):
        """One message; a malformed one gets an error answer, never a crash."""
        if not isinstance(msg, dict):
            return None
        mid = msg.get("id")
        try:
            return self._handle(msg)
        except BadParams as e:
            return _error(mid, -32602, f"invalid params: {e}") if mid is not None else None
        except Exception as e:  # a bug, or a path the system cannot take
            return _error(mid, -32603, f"internal error: {e}") if mid is not None else None

    def _handle(self, msg: dict):
        method, mid, params = msg.get("method"), msg.get("id"), msg.get("params")
        params = {} if params is None else params
        if not isinstance(params, dict):
            raise BadParams("params must be an object")
        if method == "exit":
            self.done = True
            return None
        if self.shutdown:  # after shutdown only exit is served
            return _error(mid, -32600, "the server is shutting down") if mid is not None else None
        if method == "initialize":
            caps = {"textDocumentSync": 1, "hoverProvider": True}
            return _result(mid, {"capabilities": caps, "serverInfo": {"name": "ashugh"}})
        if method == "shutdown":
            self.shutdown = True
            return _result(mid, None)
        if method == "workspace/didChangeWatchedFiles":  # a spec changed on disk
            self.reports.clear()
            return [self._publish(u) for u in self.docs]
        doc = params.get("textDocument") or {}
        if not isinstance(doc, dict):
            raise BadParams("textDocument must be an object")
        uri = doc.get("uri", "")
        if not isinstance(uri, str):
            raise BadParams("uri must be a string")
        if method == "textDocument/didOpen":
            text = doc.get("text", "")
            if not isinstance(text, str):
                raise BadParams("text must be a string")
            self.docs[uri] = text
            return [self._publish(uri)]
        if method == "textDocument/didChange":
            changes = params.get("contentChanges") or []
            if not isinstance(changes, list) or not all(isinstance(c, dict) for c in changes):
                raise BadParams("contentChanges must be a list of objects")
            if changes:
                text = changes[-1].get("text", "")
                if not isinstance(text, str):
                    raise BadParams("text must be a string")
                self.docs[uri] = text
            return [self._publish(uri)]
        if method == "textDocument/didSave":
            if _is_spec(uri):  # the songs that read this spec read it again
                self.reports.clear()
                return [self._publish(u) for u in self.docs if not _is_spec(u)]
            return [self._publish(uri)] if uri in self.docs else []
        if method == "textDocument/didClose":
            self.docs.pop(uri, None)
            self.reports.pop(uri, None)
            return [_notify("textDocument/publishDiagnostics", {"uri": uri, "diagnostics": []})]
        if method == "textDocument/hover":
            position = params.get("position") or {}
            if not isinstance(position, dict) or not isinstance(position.get("line", 0), int):
                raise BadParams("position.line must be an integer")
            return _result(mid, self._hover(uri, position))
        if mid is not None:
            return _error(mid, -32601, f"method not found: {method}")
        return None

    def _report(self, uri: str) -> tuple[Report | None, str | None]:
        text = self.docs.get(uri)
        if text is None or _is_spec(uri):
            return None, None
        cached = self.reports.get(uri)
        if cached is not None and cached[0] == text:  # hover after a change: no rescan
            return cached[1]
        path = path_of(uri)
        spec_path = find_spec(path) if path else None
        try:
            spec = load(spec_path) if spec_path else Spec()
        except (SpecError, OSError) as e:
            message = str(e)
            name = spec_path.name if spec_path else "spec"
            out: tuple[Report | None, str | None] = (
                None,
                message if name in message else f"{name}: {message}",
            )
        else:
            out = scan(text, spec, path=str(path or uri)), None
        self.reports[uri] = (text, out)
        return out

    def _publish(self, uri: str) -> dict:
        rep, problem = self._report(uri)
        diagnostics = []
        if problem:
            diagnostics.append(_diag(0, 0, 1, "spec", problem, 1))
        elif rep is not None:
            lines = lyrics.split_lines(self.docs[uri])
            used: dict[tuple[int, str], int] = {}
            for issue in rep.issues:
                row = issue.line - 1
                text = lines[row] if 0 <= row < len(lines) else ""
                message = issue.message + (f": {issue.detail}" if issue.detail else "")
                a, b = (
                    _indexed_span(text, issue)
                    or _word_span(text, message, row, used, issue.code)
                    or (
                        len(text) - len(text.lstrip()),
                        len(text),
                    )
                )
                start = _utf16(text[:a])  # LSP counts UTF-16
                diagnostics.append(
                    _diag(
                        row,
                        start,
                        max(_utf16(text[:b]), start + 1),
                        issue.code,
                        message,
                        SEVERITY[issue.severity],
                    )
                )
        return _notify("textDocument/publishDiagnostics", {"uri": uri, "diagnostics": diagnostics})

    def _hover(self, uri: str, position: dict) -> dict | None:
        rep, _ = self._report(uri)
        if rep is None:
            return None
        number = int(position.get("line", -1)) + 1
        lr = next((lr for lr in rep.lines if lr.line.number == number), None)
        if lr is None:
            return None
        if not lr.line.words:  # 1, 2, 3, 4: nothing ashugh can count
            digits = any(ch.isdigit() for ch in lr.line.text)
            value = "**no words** · " + (DIGITS if digits else "nothing to sing")
            return {"contents": {"kind": "markdown", "value": value}}
        rhyme = f" · rhyme {lr.letter}" if lr.letter and lr.letter != "-" else ""
        value = f"**{lr.fit.count} syllables** · `{lr.fit.grid}` · {lr.ending}{rhyme}\n\n{lr.sung}"
        return {"contents": {"kind": "markdown", "value": value}}


QUOTED = re.compile(r"«([^»]+)»")


def _plain(word: str) -> str:
    return word.replace(ACUTE, "").replace("-", "").lower().replace("ё", "е")


def _indexed_span(text: str, issue) -> tuple[int, int] | None:
    """The span of the words an issue names by index (an off-beat word), so of
    two мука the one off the beat is underlined."""
    at = issue.data.get("at") if isinstance(issue.data, dict) else None
    spans = lyrics.token_spans(text)
    if not at or any(not 0 <= k < len(spans) for k in at):
        return None
    return spans[at[0]][0], spans[at[-1]][1]


LINE_END_CODES = {"rhyme", "ending", "final", "scheme"}  # about the line's last word


def _word_span(
    text: str, message: str, row: int, used: dict[tuple[int, str], int], code: str = ""
) -> tuple[int, int] | None:
    """Where on its line the first word a message quotes stands («воды» read as
    во-ды́), each repeat of a note on the next occurrence, a rhyme's from the
    line's end; None if no quoted word is on the line (a rhyme partner's, say)."""
    spans = lyrics.token_spans(text)
    plain = [_plain(t) for _, _, t in spans]
    for quoted in QUOTED.findall(message):
        want = [_plain(w) for w in quoted.split()]
        n = len(want)
        found = [k for k in range(len(plain) - n + 1) if plain[k : k + n] == want]
        if found and code in LINE_END_CODES:
            k = found[-1]
            return spans[k][0], spans[k + n - 1][1]
        if found:
            key = (row, " ".join(want))
            k = found[min(used.get(key, 0), len(found) - 1)]
            used[key] = used.get(key, 0) + 1
            return spans[k][0], spans[k + n - 1][1]
    return None


def _utf16(text: str) -> int:
    """Length in UTF-16 code units, as LSP positions count: an emoji is two."""
    return len(text.encode("utf-16-le", "surrogatepass")) // 2


def _is_spec(uri: str) -> bool:
    return uri.lower().endswith(".toml")


def _error(mid, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def _diag(row: int, start: int, end: int, code: str, message: str, severity: int) -> dict:
    return {
        "range": {
            "start": {"line": row, "character": start},
            "end": {"line": row, "character": end},
        },
        "severity": severity,
        "code": code,
        "source": "ashugh",
        "message": message,
    }


def _result(mid, result) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _notify(method: str, params: dict) -> dict:
    return {"jsonrpc": "2.0", "method": method, "params": params}


def serve(stdin=None, stdout=None) -> int:
    stdin = stdin or sys.stdin.buffer
    stdout = stdout or sys.stdout.buffer
    server = Server()
    queue: list = []
    while not server.done:
        if not queue:
            queue = _read_waiting(stdin)
            if not queue:
                break
        msg = queue.pop(0)
        if msg is EOF_:
            break
        if _superseded(msg, queue):  # a later full text of the same document is waiting
            continue
        reply = server.handle(msg)
        for out in reply if isinstance(reply, list) else [reply]:
            if out is not None:
                write_message(stdout, out)
    return 0 if server.shutdown or not server.done else 1


def _read_waiting(stdin) -> list:
    """The next message, and every one already waiting behind it."""
    out: list = []
    while True:
        try:
            msg = read_message(stdin)
        except ValueError, RecursionError:  # FramingError, bad JSON, [[[[...: read on
            continue
        out.append(msg)
        if msg is EOF_ or not _ready(stdin):
            return out


def _ready(stream) -> bool:
    """Whether more input is waiting, without blocking for it."""
    try:
        return bool(select.select([stream], [], [], 0)[0])
    except AttributeError, OSError, ValueError, io.UnsupportedOperation:
        if hasattr(stream, "getbuffer"):  # an in-memory stream, as in tests
            return stream.tell() < len(stream.getbuffer())
        return False


def _superseded(msg, queue: list) -> bool:
    """A didChange that a later didChange or didClose of the same document replaces
    before any request reads it: with full sync only the last text counts, so fast
    typing costs one scan, and a hover between two changes reads the first."""
    if not isinstance(msg, dict) or msg.get("method") != "textDocument/didChange":
        return False
    uri = _uri(msg)
    if uri is None:
        return False
    for m in queue:
        if not isinstance(m, dict):
            continue
        if "id" in m and "method" in m:  # a request answers from the text so far
            return False
        if m.get("method") in ("textDocument/didChange", "textDocument/didClose"):
            if _uri(m) == uri:
                return True
    return False


def _uri(msg: dict) -> str | None:
    params = msg.get("params")
    doc = params.get("textDocument") if isinstance(params, dict) else None
    uri = doc.get("uri") if isinstance(doc, dict) else None
    return uri if isinstance(uri, str) else None
