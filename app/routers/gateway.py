import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app import nim_client, translate, usage
from app.auth import gateway_key_owner
from app.resolve import resolve_model

router = APIRouter(tags=["gateway"])


def _error(status_code: int, message: str, err_type: str = "api_error") -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"type": "error", "error": {"type": err_type, "message": message}},
    )


@router.post("/v1/messages")
async def create_message(request: Request, owner: dict = Depends(gateway_key_owner)):
    body = await request.json()
    claude_model = body.get("model", "")
    nim_model = await resolve_model(claude_model)
    payload = translate.anthropic_to_openai(body, nim_model)
    stream = bool(body.get("stream", False))

    if stream:
        async def event_gen():
            sink: dict = {}
            status = "ok"
            try:
                async with nim_client.stream_chat_completion(payload) as lines:
                    async for event in translate.openai_stream_to_anthropic(
                        lines, claude_model, usage_sink=sink
                    ):
                        yield event
            except httpx.HTTPStatusError as e:
                status = f"error_{e.response.status_code}"
                detail = await _safe_body(e.response)
                yield translate._sse(
                    "error",
                    {"type": "error", "error": {"type": "api_error", "message": detail}},
                )
            except httpx.HTTPError as e:
                status = "error_502"
                yield translate._sse(
                    "error",
                    {"type": "error", "error": {"type": "api_error", "message": str(e)}},
                )
            await usage.record(
                owner, claude_model, nim_model,
                sink.get("input_tokens", 0), sink.get("output_tokens", 0),
                streamed=True, status=status,
            )

        return StreamingResponse(event_gen(), media_type="text/event-stream")

    # Non-streaming
    try:
        resp = await nim_client.chat_completion(payload)
    except httpx.HTTPStatusError as e:
        await usage.record(owner, claude_model, nim_model, 0, 0, streamed=False,
                           status=f"error_{e.response.status_code}")
        return _error(e.response.status_code, await _safe_body(e.response))
    except httpx.HTTPError as e:
        await usage.record(owner, claude_model, nim_model, 0, 0, streamed=False, status="error_502")
        return _error(502, f"Upstream error: {e}")

    anthropic_resp = translate.openai_to_anthropic(resp, claude_model)
    u = anthropic_resp.get("usage", {})
    await usage.record(
        owner, claude_model, nim_model,
        u.get("input_tokens", 0), u.get("output_tokens", 0),
        streamed=False, status="ok",
    )
    return JSONResponse(anthropic_resp)


@router.post("/v1/messages/count_tokens")
async def count_tokens(request: Request, _owner: dict = Depends(gateway_key_owner)):
    body = await request.json()
    return {"input_tokens": translate.estimate_tokens(body)}


@router.get("/v1/models")
async def list_models(_owner: dict = Depends(gateway_key_owner)):
    """Expose NIM chat models in Anthropic /v1/models shape (for gateway model discovery)."""
    try:
        models = await nim_client.list_models()
    except httpx.HTTPError as e:
        return _error(502, f"Upstream error: {e}")
    data = [
        {"type": "model", "id": m["id"], "display_name": m["id"]}
        for m in models
    ]
    return {"data": data, "has_more": False}


async def _safe_body(response: httpx.Response) -> str:
    try:
        return (await response.aread()).decode(errors="replace")[:500]
    except Exception:
        return f"HTTP {response.status_code}"
