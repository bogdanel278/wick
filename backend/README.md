# Wick backend

FastAPI service implementing `../CONTRACT.md`.

## Run
```
pip install -r requirements.txt
ANTHROPIC_API_KEY=sk-... WICK_ENV=prod uvicorn app.main:app --port 8000
```
For local work without a key: `WICK_ENV=dev uvicorn app.main:app --reload --port 8000` (mock mode).

## Env vars
- `ANTHROPIC_API_KEY`: required. The server refuses to start without it unless `WICK_ENV=dev`.
- `WICK_ENV`: `dev` or `prod` (default behaves as prod). `dev` enables mock mode (only when no key is set), `/docs`, `/redoc`, `/openapi.json`, and `mode` in `/health`.
- `WICK_MODEL`: default `claude-sonnet-5-5`.
- `WICK_RATE_LIMIT_PER_HOUR`: per client IP, in-memory sliding window, default 10, `0` disables. State is per process and resets on restart. Behind a proxy the IP seen is the proxy's unless the proxy is the direct peer, so configure accordingly.
- `WICK_APP_KEY`: optional shared secret; if set, `POST /analyze` requires header `X-Wick-Key`. Weak protection, not app attestation.

No CORS middleware is installed (native apps do not need it).

## Limits
Images: PNG or JPEG, at most 4.5 MB, at most 8000 px per side, must decode. `instrument` and `timeframe`: at most 20 chars, `[A-Za-z0-9/._:-]`.

## Errors
`{"error": {"code", "message"}}`
- 400 `bad_image`: missing, wrong type, undecodable or too many pixels
- 400 `bad_request`: invalid `instrument` or `timeframe`
- 401 `unauthorized`: `WICK_APP_KEY` set and `X-Wick-Key` missing or wrong
- 413 `image_too_large`
- 429 `rate_limited`: per-IP limit or upstream capacity; includes `Retry-After`
- 502 `model_error`: upstream failure or output failed validation twice

## Example
```
curl -F image=@chart.png -F instrument=EURUSD -F timeframe=4h http://localhost:8000/analyze
curl http://localhost:8000/health
```

## Test
```
python -m pytest tests
```
`tests/test_analyzer.py` needs only jsonschema, Pillow and pytest; `tests/test_api.py` also needs fastapi and httpx.
