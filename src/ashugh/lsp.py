"""A language server: lines that do not scan get underlined in the editor.

    ashugh lsp

speaks the Language Server Protocol over stdio. On every open and change it
scans the document and publishes the issues as diagnostics on their lines;
hovering a line shows how it is sung. The spec is found next to the file:
<name>.toml for <name>.txt, else the nearest ashugh.toml in this or a
parent folder; without one the server reports only warnings and notes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

from .scan import Report, scan
from .spec import Spec, SpecError, load

SEVERITY = {"error": 1, "warning": 2, "info": 3}


def read_message(stream) -> dict | None:
    """One Content-Length framed JSON message, or None at the end of the stream."""
    length = None
    while True:
        line = stream.readline()
        if not line:
            return None
        line = line.strip()
        if not line:
            break
        name, _, value = line.decode("ascii", "replace").partition(":")
        if name.strip().lower() == "content-length":
            length = int(value.strip())
    if length is None:
        raise ValueError("message without Content-Length")
    return json.loads(stream.read(length).decode("utf-8"))


def write_message(stream, msg: dict) -> None:
    body = json.dumps(msg, ensure_ascii=False).encode("utf-8")
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


class Server:
    def __init__(self) -> None:
        self.docs: dict[str, str] = {}
        self.done = False
        self.shutdown = False

    def handle(self, msg: dict):
        method, mid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
        if method == "initialize":
            caps = {"textDocumentSync": 1, "hoverProvider": True}
            return _result(mid, {"capabilities": caps, "serverInfo": {"name": "ashugh"}})
        if method == "shutdown":
            self.shutdown = True
            return _result(mid, None)
        if method == "exit":
            self.done = True
            return None
        doc = params.get("textDocument") or {}
        uri = doc.get("uri", "")
        if method == "textDocument/didOpen":
            self.docs[uri] = doc.get("text", "")
            return [self._publish(uri)]
        if method == "textDocument/didChange":
            changes = params.get("contentChanges") or []
            if changes:
                self.docs[uri] = changes[-1].get("text", "")
            return [self._publish(uri)]
        if method == "textDocument/didSave":
            return [self._publish(uri)] if uri in self.docs else []
        if method == "textDocument/didClose":
            self.docs.pop(uri, None)
            return [_notify("textDocument/publishDiagnostics", {"uri": uri, "diagnostics": []})]
        if method == "textDocument/hover":
            return _result(mid, self._hover(uri, params.get("position") or {}))
        if mid is not None:
            return {
                "jsonrpc": "2.0",
                "id": mid,
                "error": {"code": -32601, "message": f"method not found: {method}"},
            }
        return None

    def _report(self, uri: str) -> tuple[Report | None, str | None]:
        text = self.docs.get(uri)
        if text is None:
            return None, None
        path = path_of(uri)
        spec_path = find_spec(path) if path else None
        try:
            spec = load(spec_path) if spec_path else Spec()
        except (SpecError, OSError) as e:
            return None, f"{spec_path.name}: {e}"
        return scan(text, spec, path=str(path or uri)), None

    def _publish(self, uri: str) -> dict:
        rep, problem = self._report(uri)
        diagnostics = []
        if problem:
            diagnostics.append(_diag(0, 0, 1, "spec", problem, 1))
        elif rep is not None:
            lines = self.docs[uri].splitlines()
            for issue in rep.issues:
                row = issue.line - 1
                text = lines[row] if 0 <= row < len(lines) else ""
                start = len(text) - len(text.lstrip())
                message = issue.message + (f": {issue.detail}" if issue.detail else "")
                diagnostics.append(
                    _diag(
                        row,
                        start,
                        max(len(text), start + 1),
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
        rhyme = f" · rhyme {lr.letter}" if lr.letter and lr.letter != "-" else ""
        value = f"**{lr.fit.count} syllables** · `{lr.fit.grid}` · {lr.ending}{rhyme}\n\n{lr.sung}"
        return {"contents": {"kind": "markdown", "value": value}}


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
    while not server.done:
        try:
            msg = read_message(stdin)
        except (ValueError, json.JSONDecodeError):
            continue
        if msg is None:
            break
        reply = server.handle(msg)
        for out in reply if isinstance(reply, list) else [reply]:
            if out is not None:
                write_message(stdout, out)
    return 0 if server.shutdown or not server.done else 1
