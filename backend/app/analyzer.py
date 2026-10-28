import base64
import json
import logging
import os
import re
import threading
import uuid
from pathlib import Path

from jsonschema import Draft202012Validator

from .prompt import PROMPT_VERSION, SYSTEM_PROMPT, build_retry_suffix, build_user_prompt

log = logging.getLogger("wick.analyzer")

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "contract" / "analysis.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text())
VALIDATOR = Draft202012Validator(SCHEMA)

DISCLAIMER = "Educational chart analysis, not financial advice."
DEFAULT_MODEL = "claude-sonnet-5-5"
MAX_PAID_CALLS = 2

BANNED_RE = re.compile(
    r"\b(buy|buying|sell|selling|take\s+profit|entry\s+point|guaranteed|will\s+definitely)\b",
    re.IGNORECASE,
)


class ModelError(Exception):
    """Failure to produce a valid analysis. Carries the HTTP mapping."""

    def __init__(self, message: str, code: str = "model_error", status: int = 502):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


class OutputInvalid(Exception):
    """Model output failed parsing, schema or wording checks (retryable)."""


def is_dev() -> bool:
    return os.environ.get("WICK_ENV") == "dev"


def is_mock() -> bool:
    return is_dev() and not os.environ.get("ANTHROPIC_API_KEY")


def model_name() -> str:
    return os.environ.get("WICK_MODEL", DEFAULT_MODEL)


def _meta() -> dict:
    return {"model": model_name()[:80], "prompt_version": PROMPT_VERSION}


def mock_response(instrument: str | None = None, timeframe: str | None = None) -> dict:
    return {
        "id": uuid.uuid4().hex[:8],
        "status": "ok",
        "chart": {"instrument": instrument or "EURUSD", "timeframe": timeframe or "4h", "chart_type": "candlestick"},
        "trend": {"direction": "up", "strength": "moderate", "summary": "Higher highs and higher lows since the swing low."},
        "levels": [
            {"type": "support", "approx_price": 1.0850, "description": "Prior swing low, tested twice."},
            {"type": "resistance", "approx_price": 1.0990, "description": "Rejected at this zone last week."},
        ],
        "patterns": [{"name": "Ascending channel", "description": "Price respecting both channel lines."}],
        "scenarios": [
            {"label": "bullish", "description": "Breakout continues the uptrend.", "trigger": "Close above 1.0990", "invalidation": "Close below 1.0850"},
            {"label": "bearish", "description": "Failed breakout turns into a range.", "trigger": "Close below 1.0850", "invalidation": "Close above 1.0990"},
        ],
        "confidence": 0.62,
        "caveats": ["Mock response: no real analysis was performed."],
        "meta": {"model": "mock", "prompt_version": PROMPT_VERSION},
        "disclaimer": DISCLAIMER,
    }


def _reject_constant(name: str):
    raise ValueError(f"non-finite number {name} is not allowed")


def _strip_fence(text: str) -> str:
    text = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S)
    return fence.group(1) if fence else text


def parse_json(text: str) -> dict:
    """Parse model text into a dict; raises OutputInvalid on any problem."""
    text = _strip_fence(text)
    try:
        try:
            data = json.loads(text, parse_constant=_reject_constant)
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start == -1 or end <= start:
                raise
            data = json.loads(text[start : end + 1], parse_constant=_reject_constant)
    except Exception as e:  # JSONDecodeError, ValueError (NaN), RecursionError, ...
        raise OutputInvalid(f"Reply is not valid JSON: {type(e).__name__}: {str(e)[:200]}") from e
    if not isinstance(data, dict):
        raise OutputInvalid("Reply must be a single JSON object.")
    return data


def _iter_strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from _iter_strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _iter_strings(v)


def find_banned(data) -> str | None:
    for s in _iter_strings(data):
        m = BANNED_RE.search(s)
        if m:
            return m.group(0)
    return None


def validate_output(data: dict) -> dict:
    """Apply server-owned fields, then check schema and wording. Raises OutputInvalid."""
    try:
        data["id"] = uuid.uuid4().hex[:8]
        data["disclaimer"] = DISCLAIMER
        data["meta"] = _meta()
        errors = sorted(VALIDATOR.iter_errors(data), key=lambda e: list(e.absolute_path))
        if errors:
            e = errors[0]
            path = "/".join(str(p) for p in e.absolute_path) or "(root)"
            raise OutputInvalid(f"Schema violation at {path}: {e.message[:200]}")
        word = find_banned(data)
        if word:
            raise OutputInvalid(f'Banned wording found: "{word}". Rewrite without trade instructions or order-type language.')
    except OutputInvalid:
        raise
    except Exception as e:
        raise OutputInvalid(f"Validation failed: {type(e).__name__}") from e
    return data


_client = None
_client_lock = threading.Lock()


def _get_client():
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                import anthropic

                _client = anthropic.Anthropic(max_retries=1, timeout=30.0)
    return _client


def _call(client, model: str, b64: str, media_type: str, user_text: str) -> str:
    resp = client.messages.create(
        model=model,
        max_tokens=2000,
        temperature=0,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text", "text": user_text},
            ],
        }],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")


def _map_upstream(e: Exception) -> ModelError:
    status = getattr(e, "status_code", None)
    request_id = getattr(e, "request_id", None)
    log.warning("upstream failure type=%s status=%s request_id=%s", type(e).__name__, status, request_id)
    if status in (429, 529):
        return ModelError("The model is at capacity. Please retry later.", code="rate_limited", status=429)
    return ModelError("The analysis service failed. Please try again.")


def analyze(image_bytes: bytes, media_type: str, instrument: str | None = None, timeframe: str | None = None) -> dict:
    if is_mock():
        return mock_response(instrument, timeframe)

    try:
        client = _get_client()
    except Exception as e:
        log.error("client init failed type=%s", type(e).__name__)
        raise ModelError("The analysis service is not available.") from e

    model = model_name()
    b64 = base64.standard_b64encode(image_bytes).decode()
    base_prompt = build_user_prompt(instrument, timeframe)
    user_text = base_prompt
    last_error = "unknown"

    for attempt in range(MAX_PAID_CALLS):
        try:
            text = _call(client, model, b64, media_type, user_text)
        except Exception as e:
            raise _map_upstream(e) from e
        try:
            return validate_output(parse_json(text))
        except OutputInvalid as e:
            last_error = str(e)
            log.warning("invalid model output attempt=%d reason=%s", attempt + 1, last_error[:200])
            user_text = base_prompt + build_retry_suffix(last_error)
    raise ModelError("The model output failed validation. Please try again.")
