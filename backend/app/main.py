import hmac
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .analyzer import ModelError, analyze, is_dev, is_mock
from .images import MAX_BYTES, BadImage, check_image, clean_hint, sniff
from .ratelimit import SlidingWindowLimiter

log = logging.getLogger("wick")

# Multipart framing and the two small text fields add a little on top of the file.
BODY_SLACK = 64 * 1024
MAX_BODY = MAX_BYTES + BODY_SLACK

limiter = SlidingWindowLimiter()


def err(status: int, code: str, message: str, headers: dict | None = None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}}, headers=headers)


def check_config() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY") and not is_dev():
        raise RuntimeError("ANTHROPIC_API_KEY is required unless WICK_ENV=dev.")


def _rate_limit() -> int:
    try:
        return int(os.environ.get("WICK_RATE_LIMIT_PER_HOUR", "10"))
    except ValueError:
        return 10


class _TooLarge(Exception):
    pass


class GuardMiddleware:
    """Pure ASGI: shared-key check, per-IP rate limit and request body size limit for POST /analyze."""

    def __init__(self, app):
        self.app = app

    async def _send_json(self, send, status, code, message, extra_headers=()):
        body = json.dumps({"error": {"code": code, "message": message}}).encode()
        headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()), *extra_headers]
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") != "POST" or scope.get("path") != "/analyze":
            return await self.app(scope, receive, send)

        headers = {k.lower(): v for k, v in scope.get("headers", [])}

        app_key = os.environ.get("WICK_APP_KEY")
        if app_key:
            supplied = headers.get(b"x-wick-key", b"")
            if not hmac.compare_digest(supplied, app_key.encode()):
                return await self._send_json(send, 401, "unauthorized", "Missing or invalid client key.")

        limit = _rate_limit()
        if limit > 0:
            client = scope.get("client")
            ip = client[0] if client else "unknown"
            wait = limiter.check(ip, limit)
            if wait is not None:
                return await self._send_json(
                    send, 429, "rate_limited", "Too many requests. Please retry later.",
                    [(b"retry-after", str(wait).encode())],
                )

        cl = headers.get(b"content-length")
        if cl is not None:
            try:
                if int(cl) > MAX_BODY:
                    return await self._send_json(send, 413, "image_too_large", "Image exceeds the 4.5 MB limit.")
            except ValueError:
                return await self._send_json(send, 400, "bad_image", "Invalid Content-Length.")

        received = 0
        started = False

        async def guarded_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > MAX_BODY:
                    raise _TooLarge()
            return message

        async def tracking_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, guarded_receive, tracking_send)
        except _TooLarge:
            if not started:
                await self._send_json(send, 413, "image_too_large", "Image exceeds the 4.5 MB limit.")


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        check_config()
        yield

    kwargs = {} if is_dev() else {"docs_url": None, "redoc_url": None, "openapi_url": None}
    application = FastAPI(title="Wick API", version="0.1", lifespan=lifespan, **kwargs)
    application.add_middleware(GuardMiddleware)

    @application.exception_handler(RequestValidationError)
    async def _validation(_: Request, __: RequestValidationError):
        return err(400, "bad_image", "Missing or invalid image upload.")

    @application.get("/health")
    def health():
        body = {"status": "ok"}
        if is_dev():
            body["mode"] = "mock" if is_mock() else "live"
        return body

    @application.post("/analyze")
    async def analyze_endpoint(
        image: UploadFile = File(...),
        instrument: str | None = Form(None),
        timeframe: str | None = Form(None),
    ):
        try:
            instrument = clean_hint("instrument", instrument)
            timeframe = clean_hint("timeframe", timeframe)
        except ValueError as e:
            return err(400, "bad_request", str(e))

        data = await image.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            return err(413, "image_too_large", "Image exceeds the 4.5 MB limit.")
        if not data:
            return err(400, "bad_image", "Image is empty.")
        media_type = sniff(data)
        if media_type is None:
            return err(400, "bad_image", "Only PNG or JPEG images are supported.")
        try:
            await run_in_threadpool(check_image, data, media_type)
        except BadImage as e:
            return err(400, "bad_image", str(e))
        try:
            return await run_in_threadpool(analyze, data, media_type, instrument, timeframe)
        except ModelError as e:
            headers = {"Retry-After": "30"} if e.status == 429 else None
            return err(e.status, e.code, e.message, headers)
        except Exception as e:
            log.error("unhandled analyze failure type=%s", type(e).__name__)
            return err(502, "model_error", "The analysis service failed. Please try again.")

    return application


app = create_app()
