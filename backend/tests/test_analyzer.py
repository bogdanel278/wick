"""Analyzer, prompt, image and rate-limit logic. Needs only jsonschema and Pillow."""
import copy
import io
import json

import pytest
from PIL import Image

from app import analyzer, images, prompt
from app.ratelimit import SlidingWindowLimiter


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("WICK_ENV", "dev")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")


def good() -> dict:
    d = analyzer.mock_response("EURUSD", "4h")
    for k in ("id", "disclaimer", "meta"):
        d.pop(k)
    return d


class Block:
    type = "text"

    def __init__(self, text):
        self.text = text


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return type("R", (), {"content": [Block(r)]})()


def run(monkeypatch, replies):
    fc = FakeClient(replies)
    monkeypatch.setattr(analyzer, "_get_client", lambda: fc)
    return fc


def test_mock_validates_and_scenarios_differ(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    r = analyzer.analyze(b"x", "image/png")
    assert not list(analyzer.VALIDATOR.iter_errors(r))
    labels = {s["label"]: s["trigger"] for s in r["scenarios"]}
    assert labels["bullish"] != labels["bearish"]
    assert r["meta"]["prompt_version"] == prompt.PROMPT_VERSION


def test_mock_only_in_dev(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    monkeypatch.setenv("WICK_ENV", "prod")
    assert not analyzer.is_mock()


def test_success_sets_server_fields(monkeypatch):
    d = good()
    d["id"] = "evil"
    d["meta"] = {"model": "x", "prompt_version": "y"}
    d["disclaimer"] = "nope"
    fc = run(monkeypatch, [json.dumps(d)])
    r = analyzer.analyze(b"x", "image/png", "EURUSD", "4h")
    assert len(fc.calls) == 1
    assert fc.calls[0]["temperature"] == 0
    assert r["id"] != "evil" and r["disclaimer"] == analyzer.DISCLAIMER
    assert r["meta"] == {"model": "claude-sonnet-5-5", "prompt_version": prompt.PROMPT_VERSION}


def test_fenced_json_ok(monkeypatch):
    run(monkeypatch, ["```json\n" + json.dumps(good()) + "\n```"])
    assert analyzer.analyze(b"x", "image/png")["status"] == "ok"


def test_retry_then_success_feeds_error_back(monkeypatch):
    fc = run(monkeypatch, ["not json at all", json.dumps(good())])
    analyzer.analyze(b"x", "image/png")
    assert len(fc.calls) == 2
    second = fc.calls[1]["messages"][0]["content"][1]["text"]
    assert "not valid JSON" in second


def test_two_failures_is_model_error_and_max_two_calls(monkeypatch):
    fc = run(monkeypatch, ["nope", "nope again", json.dumps(good())])
    with pytest.raises(analyzer.ModelError) as ei:
        analyzer.analyze(b"x", "image/png")
    assert ei.value.status == 502 and ei.value.code == "model_error"
    assert len(fc.calls) == 2


@pytest.mark.parametrize("word", ["buy", "Buying", "SELL", "selling", "take profit", "Entry   point", "guaranteed", "will definitely"])
def test_banned_wording_rejected(monkeypatch, word):
    bad = good()
    bad["scenarios"][0]["description"] = f"Traders might {word} here."
    fc = run(monkeypatch, [json.dumps(bad), json.dumps(bad)])
    with pytest.raises(analyzer.ModelError):
        analyzer.analyze(b"x", "image/png")
    assert len(fc.calls) == 2
    assert "Banned wording" in fc.calls[1]["messages"][0]["content"][1]["text"]


def test_banned_wording_retry_recovers(monkeypatch):
    bad = good()
    bad["caveats"] = ["This is guaranteed"]
    run(monkeypatch, [json.dumps(bad), json.dumps(good())])
    assert analyzer.analyze(b"x", "image/png")["status"] == "ok"


def test_whole_word_only():
    d = good()
    d["trend"]["summary"] = "Buyers and sellers are balanced; unsellable"
    assert analyzer.find_banned(d) is None


@pytest.mark.parametrize("const", ["NaN", "Infinity", "-Infinity"])
def test_nan_rejected(monkeypatch, const):
    txt = json.dumps(good()).replace('"approx_price": 1.085', f'"approx_price": {const}')
    assert const in txt
    fc = run(monkeypatch, [txt, txt])
    with pytest.raises(analyzer.ModelError):
        analyzer.analyze(b"x", "image/png")
    assert len(fc.calls) == 2


def test_schema_status_rules(monkeypatch):
    bad = good()
    bad["scenarios"] = []
    run(monkeypatch, [json.dumps(bad), json.dumps(bad)])
    with pytest.raises(analyzer.ModelError):
        analyzer.analyze(b"x", "image/png")


def test_not_a_chart_ok(monkeypatch):
    d = {"status": "not_a_chart", "chart": {"instrument": None, "timeframe": None, "chart_type": "other"},
         "trend": None, "levels": [], "patterns": [], "scenarios": [], "confidence": 0, "caveats": ["A photo."]}
    run(monkeypatch, [json.dumps(d)])
    assert analyzer.analyze(b"x", "image/png")["status"] == "not_a_chart"


def test_non_object_json(monkeypatch):
    run(monkeypatch, ["[1,2]", "[1,2]"])
    with pytest.raises(analyzer.ModelError):
        analyzer.analyze(b"x", "image/png")


class Upstream(Exception):
    def __init__(self, status):
        self.status_code = status
        self.request_id = "req_1"


@pytest.mark.parametrize("status,code,http", [(429, "rate_limited", 429), (529, "rate_limited", 429), (500, "model_error", 502), (None, "model_error", 502)])
def test_upstream_mapping_no_retry(monkeypatch, status, code, http):
    fc = run(monkeypatch, [Upstream(status), json.dumps(good())])
    with pytest.raises(analyzer.ModelError) as ei:
        analyzer.analyze(b"x", "image/png")
    assert (ei.value.code, ei.value.status) == (code, http)
    assert len(fc.calls) == 1


def test_prompt_content():
    import re
    p = prompt.SYSTEM_PROMPT
    assert not re.search(r"\b(buy|sell|buying|selling)\b", p, re.I)
    assert prompt.PROMPT_VERSION != "2026-10-28.1"
    for needle in ["DATA", "unverified", "interpolate", "not_a_chart", "CLOSE", "0.2", "0.5", "0.8"]:
        assert needle in p
    assert 'instrument="AAPL"' in prompt.build_user_prompt("AAPL", None)


def png(w, h):
    b = io.BytesIO()
    Image.new("RGB", (w, h)).save(b, "PNG")
    return b.getvalue()


def test_image_checks():
    images.check_image(png(10, 10), "image/png")
    with pytest.raises(images.BadImage):
        images.check_image(b"\x89PNG\r\n\x1a\n" + b"\0" * 50, "image/png")
    with pytest.raises(images.BadImage):
        images.check_image(png(8001, 1), "image/png")
    with pytest.raises(images.BadImage):
        images.check_image(png(10, 10), "image/jpeg")


@pytest.mark.parametrize("v", ["EURUSD", "BTC/USD", "1h", "ES=F"[:2], "", None])
def test_hint_ok(v):
    images.clean_hint("instrument", v)


@pytest.mark.parametrize("v", ["x" * 21, "a b", "ignore previous", "<script>", "a\n", "é"])
def test_hint_bad(v):
    with pytest.raises(ValueError):
        images.clean_hint("instrument", v)


def test_limiter():
    lim = SlidingWindowLimiter()
    assert all(lim.check("a", 3, now=t) is None for t in (0, 1, 2))
    assert lim.check("a", 3, now=3) > 0
    assert lim.check("b", 3, now=3) is None
    assert lim.check("a", 3, now=3601) is None
    assert lim.check("a", 0, now=3) is None
