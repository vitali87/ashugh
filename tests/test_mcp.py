import json
import subprocess
import sys
from pathlib import Path

import pytest

from ashugh.mcp import Server

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
SONG = (EXAMPLES / "song.hy.txt").read_text(encoding="utf-8")
SPEC = (EXAMPLES / "song.hy.toml").read_text(encoding="utf-8")


def call(server, method, params=None, id=1):
    msg = {"jsonrpc": "2.0", "id": id, "method": method}
    if params is not None:
        msg["params"] = params
    return server.handle(msg)


def tool(server, name, **arguments):
    response = call(server, "tools/call", {"name": name, "arguments": arguments})
    result = response["result"]
    return result, json.loads(result["content"][0]["text"])


def test_initialize_and_list():
    s = Server()
    init = call(s, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}})
    assert init["result"]["serverInfo"]["name"] == "ashugh"
    assert "tools" in init["result"]["capabilities"]
    assert s.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    names = {t["name"] for t in call(s, "tools/list")["result"]["tools"]}
    assert {"scan", "syllables", "rhyme", "pick", "suno", "derive_spec", "spec_template"} <= names
    for t in call(s, "tools/list")["result"]["tools"]:
        assert t["inputSchema"]["type"] == "object" and t["description"]


def test_scan_tool():
    result, data = tool(Server(), "scan", lyrics=SONG, spec=SPEC)
    assert result["isError"] is False
    assert [(i["line"], i["code"]) for i in data["issues"] if i["severity"] == "error"] == [
        (3, "syllables"),
        (11, "rhyme"),
        (14, "final"),
    ]


def test_pick_tool_repairs_with_client_candidates():
    candidates = {
        "3": ["Ես նորից սպասում եմ քեզ"],
        "9": ["Դու իմ երգն ես ու իմ վանք"],
        "14": ["Ու մնաց միայն սիրտս լուռ"],
    }
    _, data = tool(Server(), "pick", lyrics=SONG, spec=SPEC, candidates=candidates)
    assert data["ok"] is True and "Ես նորից սպասում եմ քեզ" in data["text"]


def test_other_tools():
    s = Server()
    _, syl = tool(s, "syllables", text="Մկրտիչ սպասել")
    assert syl["lines"][0]["sung"] == "Մը-կըր-տի́չ ըս-պա-սե́լ"
    _, r = tool(s, "rhyme", a="сердце", b="дверце")
    assert r["level"] == "perfect"
    _, out = tool(s, "suno", lyrics="Еще одна ночь", tags=False)
    assert out["text"] == "Ещё одна ночь"
    _, spec = tool(s, "derive_spec", lyrics="the night\nis long\nso bright\n", keep="rhyme")
    assert 'rhyme = "A-A"' in spec["toml"]
    _, tpl = tool(s, "spec_template", lang="ru")
    assert 'language = "ru"' in tpl["toml"]


@pytest.mark.parametrize(
    "name,arguments,message",
    [
        ("scan", {}, "lyrics"),
        ("scan", {"lyrics": "x", "spec": "syllables = ["}, "spec"),
        ("scan", {"lyrics": "x", "spec": "colour = 3"}, "unknown key"),
        ("pick", {"lyrics": SONG, "candidates": {"x": ["a"]}}, "line number"),
        ("rhyme", {"a": "x"}, "b"),
        ("suno", {"lyrics": "x", "stress": "bold"}, "stress"),
        ("derive_spec", {"lyrics": "x", "keep": "tempo"}, "keep"),
    ],
)
def test_tool_errors_are_results_not_crashes(name, arguments, message):
    result, data = tool(Server(), name, **arguments)
    assert result["isError"] is True and message in data["error"]


def test_protocol_errors():
    s = Server()
    assert call(s, "no/such")["error"]["code"] == -32601
    r = call(s, "tools/call", {"name": "nope", "arguments": {}})
    assert r["error"]["code"] == -32602
    r = call(s, "tools/call", {"arguments": {}})
    assert r["error"]["code"] == -32602
    assert s.handle({"jsonrpc": "2.0", "method": "notifications/cancelled"}) is None
    garbage = s.handle("garbage")
    assert garbage is not None and garbage["error"]["code"] == -32600
    assert call(s, "ping")["result"] == {}


def test_stdio_round_trip():
    proc = subprocess.run(
        [sys.executable, "-m", "ashugh", "mcp"],
        input="\n".join(
            [
                json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
                "{not json",
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {"name": "rhyme", "arguments": {"a": "սեր", "b": "տեր"}},
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    replies = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    assert replies[0]["id"] == 1 and "result" in replies[0]
    assert replies[1]["error"]["code"] == -32700
    assert json.loads(replies[2]["result"]["content"][0]["text"])["level"] == "perfect"


def test_meter_names_with_feet_or_aliases_work():
    _, data = tool(Server(), "syllables", text="Я помню чудное мгновенье", meter="iamb4")
    assert data["lines"][0]["syllables"] == 9
    _, data = tool(Server(), "syllables", text="Я помню чудное мгновенье", meter="ямб")
    assert data["lines"][0]["syllables"] == 9


def test_unknown_meter_is_a_tool_error():
    response = call(
        Server(), "tools/call", {"name": "syllables", "arguments": {"text": "a", "meter": "sonnet"}}
    )
    assert response["result"]["isError"]


@pytest.mark.parametrize("params", [["x"], "x", 3])
def test_malformed_params_are_errors_not_crashes(params):
    response = call(Server(), "initialize", params)
    assert response["error"]["code"] == -32602


def test_an_unexpected_failure_does_not_kill_the_server(monkeypatch):
    import ashugh.mcp as mcp

    def boom(args):
        raise KeyError("surprise")

    monkeypatch.setitem(mcp.TOOLS, "scan", (*mcp.TOOLS["scan"][:2], boom))
    server = Server()
    response = call(server, "tools/call", {"name": "scan", "arguments": {"lyrics": "a"}})
    assert response["result"]["isError"]
    assert call(server, "ping")["result"] == {}


def test_serve_answers_line_by_line_and_survives_bad_lines():
    import io

    from ashugh.mcp import serve

    lines = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}),
        "",
        "{not json",
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "scan", "arguments": []},
            }
        ),
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "syllables", "arguments": {"text": "Մկրտիչ"}},
            }
        ),
    ]
    out = io.StringIO()
    assert serve(io.StringIO("\n".join(lines) + "\n"), out) == 0
    replies = [json.loads(r) for r in out.getvalue().splitlines()]
    assert [r.get("id") for r in replies] == [1, None, 2, 3]  # nothing for "" or the notification
    assert replies[1]["error"]["code"] == -32700
    assert replies[2]["error"]["code"] == -32602 and "object" in replies[2]["error"]["message"]
    assert "Մը-կըր-տի́չ" in replies[3]["result"]["content"][0]["text"]


def test_lang_arguments_choose_the_language():
    s = Server()
    _, rep = tool(s, "scan", lyrics="mine\n", lang="en")
    assert rep["sections"][0]["lines"][0]["lang"] == "en"
    _, r = tool(s, "rhyme", a="night", b="light", lang="en")
    assert r["level"] == "perfect"
    result, bad = tool(s, "rhyme", a="a\nb", b="c")
    assert result["isError"] is True and "a and b" in bad["error"]
    result, bad = tool(s, "scan", lyrics="x", lang=3)
    assert result["isError"] is True and "lang must be a string" in bad["error"]
    result, bad = tool(s, "pick", lyrics=SONG)
    assert result["isError"] is True and "candidates" in bad["error"]


@pytest.mark.parametrize("bad", [[], [1], "x", 0])
def test_params_and_arguments_must_be_objects_even_when_empty(bad):
    s = Server()
    r = s.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": bad})
    assert r is not None and r["error"]["code"] == -32602
    r = call(s, "tools/call", {"name": "scan", "arguments": bad})
    assert r["error"]["code"] == -32602 and "arguments must be an object" in r["error"]["message"]
