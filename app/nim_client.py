import contextlib
from typing import AsyncIterator

import httpx

from app.config import settings


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if settings.nvidia_api_key:
        h["Authorization"] = f"Bearer {settings.nvidia_api_key}"
    return h


async def list_models() -> list[dict]:
    url = f"{settings.nim_base_url.rstrip('/')}/models"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=_headers())
        resp.raise_for_status()
        return resp.json().get("data", [])


async def chat_completion(payload: dict) -> dict:
    url = f"{settings.nim_base_url.rstrip('/')}/chat/completions"
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(url, headers=_headers(), json=payload)
        resp.raise_for_status()
        return resp.json()


@contextlib.asynccontextmanager
async def stream_chat_completion(payload: dict) -> AsyncIterator[AsyncIterator[str]]:
    """Yields an async iterator of raw SSE lines from NIM."""
    url = f"{settings.nim_base_url.rstrip('/')}/chat/completions"
    async with httpx.AsyncClient(timeout=300) as client:
        async with client.stream("POST", url, headers=_headers(), json=payload) as resp:
            resp.raise_for_status()
            yield resp.aiter_lines()
