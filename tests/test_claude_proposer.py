import json
from types import SimpleNamespace

import pytest

from ashugh.proposers import (
    DEFAULT_MODEL,
    SCHEMA,
    ClaudeProposer,
    ProposerError,
    Request,
    make_proposer,
)


class FakeMessages:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


def fake_client(text=None, stop_reason="end_turn", error=None):
    content = [SimpleNamespace(type="thinking", thinking="")]
    if text is not None:
        content.append(SimpleNamespace(type="text", text=text))
    messages = FakeMessages(SimpleNamespace(stop_reason=stop_reason, content=content), error)
    return SimpleNamespace(beta=SimpleNamespace(messages=messages)), messages


REQ = [Request(id="L3", line=3, lang="hy", original="Ու ես նորից սպասում եմ քեզ", syllables=8)]


def test_request_shape():
    client, messages = fake_client(json.dumps({"lines": [{"id": "L3", "candidates": []}]}))
    ClaudeProposer(client=client).propose(REQ)
    (call,) = messages.calls
    assert call["model"] == DEFAULT_MODEL == "claude-opus-5-5"
    assert call["output_config"]["format"] == {"type": "json_schema", "schema": SCHEMA}
    assert call["output_config"]["effort"] == "medium"
    assert call["fallbacks"] == "default"
    assert call["betas"] == ["server-side-fallback-2026-07-01"]
    assert "thinking" not in call and "temperature" not in call
    sent = json.loads(call["messages"][0]["content"])
    assert sent["requests"][0]["syllables"] == 8
    assert sent["requests"][0]["original"] == "Ու ես նորից սպասում եմ քեզ"


def test_parses_candidates_and_ignores_unknown_ids():
    answer = {
        "lines": [
            {"id": "L3", "candidates": [{"text": "Ես նորից սպասում եմ քեզ", "faithfulness": 0.9}]},
            {"id": "L99", "candidates": [{"text": "x", "faithfulness": 1}]},
        ]
    }
    client, _ = fake_client(json.dumps(answer, ensure_ascii=False))
    out = ClaudeProposer(client=client).propose(REQ)
    assert out == {"L3": [{"text": "Ես նորից սպասում եմ քեզ", "faithfulness": 0.9}]}


@pytest.mark.parametrize(
    "text,stop,message",
    [
        (None, "refusal", "declined"),
        ("{}", "max_tokens", "cut off"),
        ("not json", "end_turn", "JSON"),
        ('{"lines": 3}', "end_turn", "lines"),
        (None, "end_turn", "JSON"),
    ],
)
def test_bad_answers_raise(text, stop, message):
    client, _ = fake_client(text, stop)
    with pytest.raises(ProposerError, match=message):
        ClaudeProposer(client=client).propose(REQ)


def test_api_errors_are_explained():
    anthropic = pytest.importorskip("anthropic")
    import httpx2

    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    errors = [
        (
            anthropic.AuthenticationError(
                "bad", response=httpx2.Response(401, request=request), body=None
            ),
            "credentials",
        ),
        (
            anthropic.RateLimitError(
                "slow", response=httpx2.Response(429, request=request), body=None
            ),
            "rate limiting",
        ),
        (anthropic.APIConnectionError(request=request), "network"),
    ]
    for error, message in errors:
        client, _ = fake_client(error=error)
        with pytest.raises(ProposerError, match=message):
            ClaudeProposer(client=client).propose(REQ)


def test_programming_errors_are_not_swallowed():
    client, _ = fake_client(error=KeyError("bug"))
    with pytest.raises(KeyError):
        ClaudeProposer(client=client).propose(REQ)


def test_model_and_effort_are_configurable():
    client, messages = fake_client(json.dumps({"lines": []}))
    ClaudeProposer(model="claude-sonnet-5-5", effort="high", client=client).propose(REQ)
    assert messages.calls[0]["model"] == "claude-sonnet-5-5"
    assert messages.calls[0]["output_config"]["effort"] == "high"


def test_make_proposer_specs(tmp_path, monkeypatch):
    monkeypatch.delenv("ASHUGH_PROPOSER", raising=False)
    assert isinstance(make_proposer(None), ClaudeProposer)
    assert make_proposer("cmd:python -c pass").argv == ["python", "-c", "pass"]
    path = tmp_path / "c.json"
    path.write_text('{"1": ["a"]}', encoding="utf-8")
    assert make_proposer(f"file:{path}").candidates == {1: ["a"]}
    monkeypatch.setenv("ASHUGH_PROPOSER", f"file:{path}")
    assert make_proposer(None).candidates == {1: ["a"]}
    for bad in ["gpt", "cmd:", "file:/nonexistent/x.json"]:
        with pytest.raises(ProposerError):
            make_proposer(bad)
