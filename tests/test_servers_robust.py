"""One bad message must not take a server down or out of step."""

import io
import json

from ashugh import lsp, mcp


def mcp_run(*lines: str) -> list:
    out = io.StringIO()
    mcp.serve(io.StringIO("".join(line + "\n" for line in lines)), out)
    text = out.getvalue()
    assert text.isascii()  # a lone surrogate cannot break the encoding
    return [json.loads(line) for line in text.splitlines()]


PING = '{"jsonrpc":"2.0","id":99,"method":"ping"}'


def test_mcp_survives_a_lone_surrogate():
    call = (
        '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"scan",'
        '"arguments":{"lyrics":"love \\ud83d you\\nabove"}}}'
    )
    replies = mcp_run(call, PING)
    assert [r["id"] for r in replies] == [1, 99] and "result" in replies[0]


def test_mcp_answers_malformed_requests_instead_of_dying():
    bad_name = '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":["scan"]}}'
    deep = "[" * 100000 + "]" * 100000
    null_id = '{"jsonrpc":"2.0","id":null,"method":"ping"}'
    bad_method = '{"jsonrpc":"2.0","id":3,"method":7}'
    nan_id = '{"jsonrpc":"2.0","id":NaN,"method":"ping"}'
    replies = mcp_run(bad_name, deep, null_id, bad_method, nan_id, PING)
    codes = [r.get("error", {}).get("code") for r in replies]
    assert codes == [-32602, -32700, -32600, -32600, -32600, None]
    assert replies[-1]["id"] == 99


def test_mcp_takes_a_batch():
    batch = '[{"jsonrpc":"2.0","id":1,"method":"ping"},{"jsonrpc":"2.0","method":"x"}]'
    (reply,) = mcp_run(batch)
    assert reply == [{"jsonrpc": "2.0", "id": 1, "result": {}}]


def tool(name: str, **arguments):
    reply = mcp.Server().handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )
    assert reply is not None
    result = reply["result"]
    return result["isError"], json.loads(result["content"][0]["text"])


def test_mcp_pick_names_what_it_ignored():
    failed, data = tool("pick", lyrics="I walk the way\n", candidates={"999": ["x y z"]})
    assert not failed and data["warnings"] == [
        "line 999 is no lyric line (lines count from the file's first)"
    ]


def test_mcp_suno_takes_tags_as_a_boolean_only():
    failed, _ = tool("suno", lyrics="Я жду", tags="false")
    assert failed
    failed, data = tool("suno", lyrics="Я жду", tags=False)
    assert not failed and data["text"] == "Я жду"


def test_mcp_schemas_declare_what_the_tools_take():
    reply = mcp.Server().handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert reply is not None
    tools = {t["name"]: t["inputSchema"]["properties"] for t in reply["result"]["tools"]}
    assert tools["suno"]["lang"]["enum"] == ["hy", "ru", "en"]
    assert tools["suno"]["armenian"]["enum"] == ["script", "schwa", "latin"]
    assert "spec" in tools["syllables"]
    assert tools["pick"]["candidates"]["type"] == ["object", "array"]


def frame(body: bytes, length: str | None = None) -> bytes:
    return b"Content-Length: %s\r\n\r\n" % (length or str(len(body))).encode() + body


def lsp_run(stream: bytes) -> list[dict]:
    out = io.BytesIO()
    lsp.serve(io.BytesIO(stream), out)
    data, msgs = out.getvalue(), []
    assert data.isascii()
    while data:
        head, _, rest = data.partition(b"\r\n\r\n")
        n = int(head.split(b":")[1])
        msgs.append(json.loads(rest[:n]))
        data = rest[n:]
    return msgs


def msg(**fields) -> bytes:
    return json.dumps({"jsonrpc": "2.0", **fields}).encode()


def test_lsp_finds_its_step_again_after_a_bad_header():
    good = frame(msg(id=7, method="shutdown"))
    stream = frame(b'{"id":1}', "abc") + frame(b'{"id":2}', "-1") + good
    assert [m.get("id") for m in lsp_run(stream)] == [7]


def test_lsp_answers_malformed_params_and_reads_null_as_no_message():
    stream = (
        frame(b"null")
        + frame(msg(id=1, method="textDocument/hover", params=[1]))
        + frame(msg(id=2, method="textDocument/hover", params={"textDocument": "x"}))
        + frame(
            msg(method="textDocument/didOpen", params={"textDocument": {"uri": "u", "text": 5}})
        )
        + frame(
            msg(
                method="textDocument/didChange",
                params={"textDocument": {"uri": "u"}, "contentChanges": {}},
            )
        )
        + frame(msg(id=3, method="shutdown"))
    )
    replies = {m.get("id"): m for m in lsp_run(stream) if "id" in m}
    assert replies[1]["error"]["code"] == -32602 and replies[2]["error"]["code"] == -32602
    assert replies[3]["result"] is None


def test_lsp_survives_a_lone_surrogate_in_a_uri():
    body = (
        b'{"jsonrpc":"2.0","method":"textDocument/didOpen","params":{"textDocument":'
        b'{"uri":"file:///tmp/a\\ud83d.txt","text":"I walk"}}}'
    )
    stream = frame(body) + frame(msg(id=3, method="shutdown"))
    assert any(m.get("id") == 3 for m in lsp_run(stream))


def test_lsp_ranges_count_utf16_units():
    server = lsp.Server()
    line = "  I love you \U0001f600\U0001f600\U0001f600 so much tonight my dear 1"
    (pub,) = server.handle(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": "u", "text": line}},
        }
    )
    (diag,) = pub["params"]["diagnostics"]
    assert diag["range"]["start"]["character"] == 2
    assert diag["range"]["end"]["character"] == len(line.encode("utf-16-le")) // 2


def test_lsp_refuses_requests_after_shutdown():
    server = lsp.Server()
    server.handle({"jsonrpc": "2.0", "id": 1, "method": "shutdown"})
    reply = server.handle({"jsonrpc": "2.0", "id": 2, "method": "textDocument/hover", "params": {}})
    assert reply["error"]["code"] == -32600


def test_lsp_rescans_open_lyrics_when_their_spec_is_saved(tmp_path):
    song, spec = tmp_path / "song.txt", tmp_path / "song.toml"
    song.write_text("I walk the way\n", encoding="utf-8")
    spec.write_text("syllables = 4\n", encoding="utf-8")
    server = lsp.Server()
    open_ = {"textDocument": {"uri": song.as_uri(), "text": "I walk the way\n"}}
    server.handle({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": open_})
    spec.write_text("syllables = 5\n", encoding="utf-8")
    pubs = server.handle(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didSave",
            "params": {"textDocument": {"uri": spec.as_uri()}},
        }
    )
    (pub,) = [p for p in pubs if p["params"]["uri"] == song.as_uri()]
    assert [d["code"] for d in pub["params"]["diagnostics"]] == ["syllables"]


def test_lsp_does_not_read_a_spec_as_lyrics(tmp_path):
    spec = tmp_path / "song.toml"
    server = lsp.Server()
    (pub,) = server.handle(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": spec.as_uri(), "text": "syllables = 8\n"}},
        }
    )
    assert pub["params"]["diagnostics"] == []


def test_lsp_names_a_bad_spec_once(tmp_path):
    song, spec = tmp_path / "song.txt", tmp_path / "song.toml"
    spec.write_text("syllables = 'eight'\n", encoding="utf-8")
    server = lsp.Server()
    (pub,) = server.handle(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": song.as_uri(), "text": "x"}},
        }
    )
    message = pub["params"]["diagnostics"][0]["message"]
    assert message.count("song.toml") == 1


def test_mcp_reads_a_line_that_opens_with_a_byte_order_mark():
    (reply,) = mcp_run("﻿" + PING)
    assert reply == {"jsonrpc": "2.0", "id": 99, "result": {}}


def test_lsp_scans_only_the_last_of_the_changes_already_queued():
    def change(n: int) -> bytes:
        params = {
            "textDocument": {"uri": "u", "version": n},
            "contentChanges": [{"text": f"I walk {n}"}],
        }
        return frame(msg(method="textDocument/didChange", params=params))

    opened = frame(
        msg(method="textDocument/didOpen", params={"textDocument": {"uri": "u", "text": "x"}})
    )
    stream = opened + b"".join(change(n) for n in range(30)) + frame(msg(id=1, method="shutdown"))
    pubs = [m for m in lsp_run(stream) if m.get("method") == "textDocument/publishDiagnostics"]
    assert len(pubs) == 2  # the open and the last change, not 31 scans
