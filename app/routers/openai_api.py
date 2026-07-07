"""OpenAI-compatible endpoints.

NVIDIA NIM already speaks the OpenAI Chat Completions API, so these are largely
a smart passthrough: authenticate the gateway key, resolve the model slot to a
NIM model, then forward — while reusing the same caching, rate limits, metrics
and usage tracking as the Anthropic path. This lets any OpenAI-format client
(OpenAI SDK, Cline, Continue, LangChain, LiteLLM, …) use the gateway."""
import time

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app import cache, limits, metrics, nim_client, usage
from app.auth import gateway_key_owner
from app.resolve import resolve_model

router = APIRouter(prefix="/openai/v1", tags=["openai"])


def _error(status_code: int, message: str, err_type: str = "invalid_request_error") -> JSONResponse:
    # OpenAI-shaped error envelope.
    return JSONResponse(
        status_code=status_code,
        content={"error": {"message": message, "type": err_type, "code": None}},
    )


def _extract_usage(resp: dict) -> tuple[int, int]:
    u = resp.get("usage") or {}
    return u.get("prompt_tokens", 0) or 0, u.get("completion_tokens", 0) or 0


@router.get("/models")
async def list_models(_owner: dict = Depends(gateway_key_owner)):
    """OpenAI /models shape, listing NIM chat + mapped slot aliases."""
    try:
        models = await nim_client.list_models()
    except httpx.HTTPError as e:
        return _error(502, f"Upstream error: {e}", "api_error")
    data = [{"id": m["id"], "object": "model", "owned_by": m.get("owned_by", "nvidia")}
            for m in models]
    return {"object": "list", "data": data}


@router.post("/chat/completions")
async def chat_completions(request: Request, owner: dict = Depends(gateway_key_owner)):
    allowed, reason = await limits.check(owner)
    if not allowed:
        return _error(429, reason, "rate_limit_error")

    body = await request.json()
    requested = body.get("model", "")
    # Resolve slot aliases (opus/sonnet/haiku/claude-*) to a NIM model, but pass
    # a raw NIM id straight through.
    nim_model = await resolve_model(requested)
    payload = dict(body)
    payload["model"] = nim_model
    stream = bool(body.get("stream", False))

    if stream:
        async def event_gen():
            status = "ok"
            in_tok = out_tok = 0
            start = time.monotonic()
            try:
                async with nim_client.stream_chat_completion(payload) as lines:
                    async for line in lines:
                        # NIM emits OpenAI SSE already — forward verbatim.
                        if line:
                            yield line + "\n"
                            if line.startswith("data:"):
                                data = line[5:].strip()
                                if data and data != "[DONE]":
                                    import json as _json
                                    try:
                                        chunk = _json.loads(data)
                                        u = chunk.get("usage")
                                        if u:
                                            in_tok = u.get("prompt_tokens", in_tok) or in_tok
                                            out_tok = u.get("completion_tokens", out_tok) or out_tok
                                    except ValueError:
                                        pass
                        else:
                            yield "\n"
            except httpx.HTTPStatusError as e:
                status = f"error_{e.response.status_code}"
            except httpx.HTTPError:
                status = "error_502"
            metrics.record_latency(time.monotonic() - start)
            metrics.record_request(nim_model, status, in_tok, out_tok)
            await usage.record(owner, requested, nim_model, in_tok, out_tok,
                               streamed=True, status=status)

        return StreamingResponse(event_gen(), media_type="text/event-stream")

    # Non-streaming — cache, forward, record.
    cached_resp = await cache.get(payload, namespace="openai")
    if cached_resp is not None:
        metrics.record_cache(hit=True)
        return JSONResponse(cached_resp)
    metrics.record_cache(hit=False)

    start = time.monotonic()
    try:
        resp = await nim_client.chat_completion(payload)
    except httpx.HTTPStatusError as e:
        metrics.record_request(nim_model, f"error_{e.response.status_code}", 0, 0)
        await usage.record(owner, requested, nim_model, 0, 0, streamed=False,
                           status=f"error_{e.response.status_code}")
        detail = (await _safe_body(e.response))
        return _error(e.response.status_code, detail, "api_error")
    except httpx.HTTPError as e:
        metrics.record_request(nim_model, "error_502", 0, 0)
        await usage.record(owner, requested, nim_model, 0, 0, streamed=False, status="error_502")
        return _error(502, f"Upstream error: {e}", "api_error")

    metrics.record_latency(time.monotonic() - start)
    in_tok, out_tok = _extract_usage(resp)
    metrics.record_request(nim_model, "ok", in_tok, out_tok)
    await usage.record(owner, requested, nim_model, in_tok, out_tok, streamed=False, status="ok")
    await cache.put(payload, resp, namespace="openai")
    return JSONResponse(resp)


async def _safe_body(response: httpx.Response) -> str:
    try:
        return (await response.aread()).decode(errors="replace")[:500]
    except Exception:
        return f"HTTP {response.status_code}"
