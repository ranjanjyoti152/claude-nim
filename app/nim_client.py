import contextlib
import itertools
import threading
from typing import AsyncIterator

import httpx

from app.config import settings

# Round-robin cursor across configured backends.
_rr_lock = threading.Lock()
_rr_counter = itertools.count()


def _headers(api_key: str) -> dict:
    h = {"Content-Type": "application/json"}
    if api_key:
        h["Authorization"] = f"Bearer {api_key}"
    return h


def _ordered_backends() -> list[dict]:
    """Return backends starting at the next round-robin index (for failover order)."""
    backends = settings.backends()
    if len(backends) <= 1:
        return backends
    with _rr_lock:
        start = next(_rr_counter) % len(backends)
    return backends[start:] + backends[:start]


async def list_models() -> list[dict]:
    # Model catalog comes from the primary backend.
    b = settings.backends()[0]
    url = f"{b['base_url'].rstrip('/')}/models"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=_headers(b["api_key"]))
        resp.raise_for_status()
        return resp.json().get("data", [])


async def chat_completion(payload: dict) -> dict:
    """Non-streaming completion with round-robin + failover across backends.

    Fails over only on connection errors and 5xx (transient); a 4xx (e.g. 404
    model-not-found) is returned immediately since retrying won't help.
    """
    last_exc: Exception | None = None
    for b in _ordered_backends():
        url = f"{b['base_url'].rstrip('/')}/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                resp = await client.post(url, headers=_headers(b["api_key"]), json=payload)
                if resp.status_code >= 500:
                    resp.raise_for_status()
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code < 500:
                raise  # client error — don't fail over
            last_exc = e
        except httpx.HTTPError as e:
            last_exc = e
    if last_exc:
        raise last_exc
    raise RuntimeError("No NIM backends configured")


@contextlib.asynccontextmanager
async def stream_chat_completion(payload: dict) -> AsyncIterator[AsyncIterator[str]]:
    """Streaming completion with failover on connect/5xx before first byte."""
    last_exc: Exception | None = None
    for b in _ordered_backends():
        url = f"{b['base_url'].rstrip('/')}/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                async with client.stream(
                    "POST", url, headers=_headers(b["api_key"]), json=payload
                ) as resp:
                    if resp.status_code >= 400:
                        # Read the error body then decide whether to fail over.
                        await resp.aread()
                        if resp.status_code < 500:
                            resp.raise_for_status()
                        resp.raise_for_status()
                    yield resp.aiter_lines()
                    return
        except httpx.HTTPStatusError as e:
            if e.response.status_code < 500:
                raise
            last_exc = e
        except httpx.HTTPError as e:
            last_exc = e
    if last_exc:
        raise last_exc
    raise RuntimeError("No NIM backends configured")


async def probe(model: str) -> dict:
    """Fire a tiny completion to check whether a model is actually runnable.

    Returns {ok, status, detail, latency_ms}.
    """
    import time

    b = settings.backends()[0]
    url = f"{b['base_url'].rstrip('/')}/chat/completions"
    payload = {"model": model, "max_tokens": 1, "messages": [{"role": "user", "content": "hi"}]}
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, headers=_headers(b["api_key"]), json=payload)
        latency = int((time.monotonic() - start) * 1000)
        if resp.status_code == 200:
            return {"ok": True, "status": 200, "detail": "runnable", "latency_ms": latency}
        return {
            "ok": False,
            "status": resp.status_code,
            "detail": resp.text[:200],
            "latency_ms": latency,
        }
    except httpx.HTTPError as e:
        return {"ok": False, "status": 0, "detail": str(e), "latency_ms": None}
