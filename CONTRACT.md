# Wick API Contract (v0.1)

Single source of truth for the backend, app and eval work. If you need to change it, say so in your report instead of editing it silently.

## Endpoints

### `GET /health`
Returns `{"status": "ok"}`. When `WICK_ENV=dev` it also includes `"mode": "live" | "mock"`.

### `POST /analyze`
`multipart/form-data`

| field | type | required | notes |
|---|---|---|---|
| `image` | file | yes | PNG or JPEG, max 4.5 MB (the model API limit is 5 MB). Apps should downscale and compress before upload. |
| `instrument` | string | no | e.g. `EURUSD`, `AAPL`. Hint only. |
| `timeframe` | string | no | e.g. `1h`, `4h`, `1D`. Hint only. |

**200 response**: JSON that validates against `contract/analysis.schema.json`.

```json
{
  "id": "a1b2c3",
  "status": "ok",
  "chart": { "instrument": "EURUSD", "timeframe": "4h", "chart_type": "candlestick" },
  "trend": { "direction": "up", "strength": "moderate", "summary": "Higher highs and higher lows since the swing low." },
  "levels": [
    { "type": "support", "approx_price": 1.0850, "description": "Prior swing low, tested twice." },
    { "type": "resistance", "approx_price": 1.0990, "description": "Rejected at this zone last week." }
  ],
  "patterns": [ { "name": "Ascending channel", "description": "Price respecting both channel lines." } ],
  "scenarios": [
    { "label": "bullish", "description": "Breakout continues the uptrend.", "trigger": "Close above 1.0990", "invalidation": "Close below 1.0850" },
    { "label": "bearish", "description": "Failed breakout turns into a range.", "trigger": "Close below 1.0850", "invalidation": "Close above 1.0990" }
  ],
  "confidence": 0.62,
  "caveats": ["Price labels partly cut off; levels are approximate."],
  "meta": { "model": "claude-sonnet-5-5", "prompt_version": "2026-10-28.1" },
  "disclaimer": "Educational chart analysis, not financial advice."
}
```

**Not a chart**: `status` is `"not_a_chart"`, and `trend`, `levels`, `patterns`, `scenarios` are empty or null as the schema allows; `caveats` explains why.

**Errors**: `{"error": {"code": "<string>", "message": "<string>"}}` with HTTP status:
- 400 `bad_image` (missing, wrong type, unreadable)
- 400 `bad_request` (invalid `instrument` or `timeframe` hint)
- 401 `unauthorized` (only when `WICK_APP_KEY` is set and `X-Wick-Key` is missing or wrong)
- 413 `image_too_large`
- 502 `model_error` (upstream failure or output failed validation twice)
- 429 `rate_limited` (per-client limit, or upstream model capacity; message says to retry later)

## Rules
- Numbers are `null` when not legible on the chart. Never invent prices.
- `confidence` is 0 to 1 and reflects image clarity and pattern clarity, not a prediction of the market.
- Output is framed as educational analysis. No "buy", "sell" or "guaranteed" language.
- `disclaimer` is always present (set server-side).
- `meta` is set server-side so eval results can be tied to a model and prompt version.
- `trend.direction` describes the visible chart, not a forecast: net close-to-close move across the visible window plus higher-high/higher-low (or lower-high/lower-low) structure; `sideways` when the net move is small relative to the typical bar range; `unclear` when it cannot be read.
- `confidence` means clarity of the image and pattern, not the chance the market moves a given way. Bands: about 0.2 for low-res, cropped or cluttered; about 0.5 for readable but mixed signals; about 0.8 for a clean chart with legible axis and clear structure.
- Prices: read the two nearest axis labels and interpolate, to the precision of the axis ticks. If the axis is cropped or unreadable, `approx_price` is `null`.
- Scenarios are illustrative. `trigger` and `invalidation` are tied to a close on the chart's timeframe (not a wick), numeric when the axis is legible, and the invalidation sits on the opposite side of the trigger. At least one scenario when `status` is `ok`.
- `not_a_chart` implies `trend` is null and `levels`, `patterns`, `scenarios` are empty. The schema enforces this.
- Banned wording in any text field: buy/buying, sell/selling, take profit, entry point, guaranteed, "will definitely". The backend enforces this and retries or fails with `model_error`.
- `instrument` and `timeframe` are unverified user hints: at most 20 characters, `^[A-Za-z0-9/._:-]*$`. They must never override what is visible on the chart.
- Backend config via env: `ANTHROPIC_API_KEY`, `WICK_MODEL` (default `claude-sonnet-5-5`), `WICK_ENV` (`dev` or `prod`). Mock mode (canned valid response) is allowed only when `WICK_ENV=dev` and no API key is set; in any other case a missing key makes the server fail at startup. `WICK_RATE_LIMIT_PER_HOUR` (default 10 per client IP, 0 disables), `WICK_APP_KEY` (optional shared secret expected in an `X-Wick-Key` header; weak protection, not a substitute for app attestation).
