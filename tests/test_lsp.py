import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from ashugh.lsp import Server, find_spec, read_message, write_message

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def frame(msg) -> bytes:
    body = json.dumps(msg, ensure_ascii=False).encode()
    return b"Content-Length: %d\r\n\r\n" % len(body) + body


def open_doc(server, uri, text, version=1):
    return server.handle(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {
                    "uri": uri,
                    "languageId": "lyrics",
                    "version": version,
                    "text": text,
                }
            },
        }
    )


def test_find_spec_prefers_the_sibling(tmp_path):
    song = tmp_path / "song.txt"
    song.write_text("x", encoding="utf-8")
    assert find_spec(song) is None
    (tmp_path / "ashugh.toml").write_text("syllables = 8", encoding="utf-8")
    assert find_spec(song) == tmp_path / "ashugh.toml"
    (tmp_path / "song.toml").write_text("syllables = 8", encoding="utf-8")
    assert find_spec(song) == tmp_path / "song.toml"


def test_find_spec_walks_up(tmp_path):
    (tmp_path / "ashugh.toml").write_text("syllables = 8", encoding="utf-8")
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)
    assert find_spec(deep / "s.txt") == tmp_path / "ashugh.toml"


def test_diagnostics_for_the_example(tmp_path):
    song = tmp_path / "song.hy.txt"
    song.write_text((EXAMPLES / "song.hy.txt").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "song.hy.toml").write_text(
        (EXAMPLES / "song.hy.toml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    server = Server()
    notes = open_doc(server, song.as_uri(), song.read_text(encoding="utf-8"))
    (publish,) = notes
    assert publish["method"] == "textDocument/publishDiagnostics"
    diags = publish["params"]["diagnostics"]
    errors = [(d["range"]["start"]["line"], d["code"]) for d in diags if d["severity"] == 1]
    assert errors == [(2, "syllables"), (10, "rhyme"), (13, "final")]
    first = next(d for d in diags if d["code"] == "syllables" and d["severity"] == 1)
    assert first["range"]["start"]["character"] == 0
    assert "ըս-պա-սում" in first["message"] and first["source"] == "ashugh"


def test_change_republishes_and_close_clears(tmp_path):
    (tmp_path / "ashugh.toml").write_text("syllables = 4", encoding="utf-8")
    uri = (tmp_path / "s.txt").as_uri()
    server = Server()
    (first,) = open_doc(server, uri, "Я жду")
    assert first["params"]["diagnostics"] and first["params"]["diagnostics"][0]["severity"] == 1
    (changed,) = server.handle(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didChange",
            "params": {
                "textDocument": {"uri": uri, "version": 2},
                "contentChanges": [{"text": "Я жду тебя"}],
            },
        }
    )
    assert [d for d in changed["params"]["diagnostics"] if d["severity"] == 1] == []
    (closed,) = server.handle(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didClose",
            "params": {"textDocument": {"uri": uri}},
        }
    )
    assert closed["params"]["diagnostics"] == []


def test_hover_shows_the_sung_line(tmp_path):
    uri = (tmp_path / "s.txt").as_uri()
    server = Server()
    open_doc(server, uri, "[Verse]\nՄկրտիչն էլ է սպասում\n")
    reply = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "textDocument/hover",
            "params": {"textDocument": {"uri": uri}, "position": {"line": 1, "character": 3}},
        }
    )
    value = reply["result"]["contents"]["value"]
    assert "ըս-պա-սում" in value and "syllables" in value
    empty = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "textDocument/hover",
            "params": {"textDocument": {"uri": uri}, "position": {"line": 0, "character": 0}},
        }
    )
    assert empty["result"] is None


def test_lifecycle_and_errors():
    server = Server()
    init = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    caps = init["result"]["capabilities"]
    assert caps["textDocumentSync"] == 1 and caps["hoverProvider"] is True
    assert server.handle({"jsonrpc": "2.0", "id": 2, "method": "nope"})["error"]["code"] == -32601
    hover = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "textDocument/hover",
            "params": {
                "textDocument": {"uri": "file:///missing.txt"},
                "position": {"line": 0, "character": 0},
            },
        }
    )
    assert hover["result"] is None
    assert server.handle({"jsonrpc": "2.0", "id": 4, "method": "shutdown"})["result"] is None
    assert server.handle({"jsonrpc": "2.0", "method": "exit"}) is None and server.done


def test_bad_spec_is_one_diagnostic(tmp_path):
    (tmp_path / "ashugh.toml").write_text("syllables = [", encoding="utf-8")
    (publish,) = open_doc(Server(), (tmp_path / "s.txt").as_uri(), "Я жду")
    (diag,) = publish["params"]["diagnostics"]
    assert diag["severity"] == 1 and "ashugh.toml" in diag["message"]


def test_framing_round_trip():
    buf = io.BytesIO()
    write_message(buf, {"jsonrpc": "2.0", "id": 1, "result": "ок"})
    buf.seek(0)
    assert read_message(buf) == {"jsonrpc": "2.0", "id": 1, "result": "ок"}
    assert read_message(io.BytesIO(b"")) is None
    with pytest.raises(ValueError):
        read_message(io.BytesIO(b"Content-Type: x\r\n\r\n{}"))


def test_stdio_session(tmp_path):
    uri = (tmp_path / "s.txt").as_uri()
    stream = b"".join(
        [
            frame({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
            frame({"jsonrpc": "2.0", "method": "initialized", "params": {}}),
            frame(
                {
                    "jsonrpc": "2.0",
                    "method": "textDocument/didOpen",
                    "params": {
                        "textDocument": {
                            "uri": uri,
                            "languageId": "lyrics",
                            "version": 1,
                            "text": "Я жду",
                        }
                    },
                }
            ),
            frame({"jsonrpc": "2.0", "id": 2, "method": "shutdown"}),
            frame({"jsonrpc": "2.0", "method": "exit"}),
        ]
    )
    proc = subprocess.run(
        [sys.executable, "-m", "ashugh", "lsp"], input=stream, capture_output=True, timeout=60
    )
    out = io.BytesIO(proc.stdout)
    replies = []
    while (msg := read_message(out)) is not None:
        replies.append(msg)
    assert replies[0]["id"] == 1
    assert any(r.get("method") == "textDocument/publishDiagnostics" for r in replies)
    assert replies[-1]["id"] == 2
    assert proc.returncode == 0


def test_diagnostics_use_editor_line_numbers(tmp_path):
    (tmp_path / "song.toml").write_text("syllables = 3\n", encoding="utf-8")
    uri = (tmp_path / "song.txt").as_uri()
    (published,) = open_doc(Server(), uri, "Я жду\u2028тебя\nЯ жду тебя всю ночь до утра\n")
    rows = {d["range"]["start"]["line"] for d in published["params"]["diagnostics"]}
    assert rows == {0, 1}


def _replies(raw: bytes) -> list[dict]:
    stream, out = io.BytesIO(raw), []
    while (msg := read_message(stream)) is not None:
        out.append(msg)
    return out


def test_serve_survives_bad_frames_and_exits_cleanly(tmp_path):
    from ashugh.lsp import serve

    uri = (tmp_path / "song.txt").as_uri()
    raw = b"".join(
        [
            frame({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
            b"X-Nonsense: 1\r\n\r\n",  # no Content-Length
            b"Content-Length: many\r\n\r\n",
            b"Content-Length: 5\r\n\r\n\xff\xfe{}}",  # not UTF-8
            frame(
                {
                    "jsonrpc": "2.0",
                    "method": "textDocument/didOpen",
                    "params": {"textDocument": {"uri": uri, "version": 1, "text": "Я жду"}},
                }
            ),
            frame({"jsonrpc": "2.0", "id": 2, "method": "shutdown"}),
            frame({"jsonrpc": "2.0", "method": "exit"}),
            frame({"jsonrpc": "2.0", "id": 3, "method": "initialize", "params": {}}),  # after exit
        ]
    )
    out = io.BytesIO()
    assert serve(io.BytesIO(raw), out) == 0
    replies = _replies(out.getvalue())
    assert [r.get("id", r.get("method")) for r in replies] == [
        1,
        "textDocument/publishDiagnostics",
        2,
    ]


def test_exit_without_shutdown_is_exit_code_1():
    from ashugh.lsp import serve

    raw = frame({"jsonrpc": "2.0", "method": "exit"})
    assert serve(io.BytesIO(raw), io.BytesIO()) == 1
    assert serve(io.BytesIO(b""), io.BytesIO()) == 0  # the client just went away
