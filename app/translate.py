"""Bidirectional translation between the Anthropic Messages API and the
OpenAI Chat Completions API (as spoken by NVIDIA NIM)."""
import json
import time
import uuid
from typing import AsyncIterator, Optional

# ---------------------------------------------------------------------------
# Anthropic request  ->  OpenAI request
# ---------------------------------------------------------------------------


def _system_to_text(system) -> Optional[str]:
    if system is None:
        return None
    if isinstance(system, str):
        return system
    # List of content blocks -> concatenate text (ignore cache_control).
    parts = []
    for block in system:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
        elif isinstance(block, str):
            parts.append(block)
    return "\n\n".join(parts) if parts else None


def _content_to_openai(content) -> tuple[Optional[str | list], list[dict]]:
    """Return (openai_content, tool_calls). tool_calls only set for assistant."""
    if isinstance(content, str):
        return content, []

    text_parts: list[dict] = []
    tool_calls: list[dict] = []
    for block in content:
        btype = block.get("type")
        if btype == "text":
            text_parts.append({"type": "text", "text": block.get("text", "")})
        elif btype == "image":
            src = block.get("source", {})
            if src.get("type") == "base64":
                data_url = f"data:{src.get('media_type','image/png')};base64,{src.get('data','')}"
                text_parts.append({"type": "image_url", "image_url": {"url": data_url}})
            elif src.get("type") == "url":
                text_parts.append({"type": "image_url", "image_url": {"url": src.get("url")}})
        elif btype == "tool_use":
            tool_calls.append(
                {
                    "id": block.get("id"),
                    "type": "function",
                    "function": {
                        "name": block.get("name"),
                        "arguments": json.dumps(block.get("input", {})),
                    },
                }
            )
        # tool_result handled at the message level (needs its own role)

    # Collapse a single text part to a plain string (many models prefer it).
    if len(text_parts) == 1 and text_parts[0]["type"] == "text":
        return text_parts[0]["text"], tool_calls
    if not text_parts:
        return None, tool_calls
    return text_parts, tool_calls


def _extract_tool_results(content) -> list[dict]:
    """Pull tool_result blocks out of a user message into OpenAI tool messages."""
    results = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                c = block.get("content", "")
                if isinstance(c, list):
                    c = "".join(
                        b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text"
                    )
                results.append(
                    {
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id"),
                        "content": c if isinstance(c, str) else json.dumps(c),
                    }
                )
    return results


def anthropic_to_openai(body: dict, nim_model: str) -> dict:
    messages: list[dict] = []

    system_text = _system_to_text(body.get("system"))
    if system_text:
        messages.append({"role": "system", "content": system_text})

    for msg in body.get("messages", []):
        role = msg.get("role")
        content = msg.get("content")

        if role == "user":
            tool_results = _extract_tool_results(content)
            # Emit tool results as separate tool-role messages first.
            messages.extend(tool_results)
            # Then any non-tool_result content as a normal user message.
            if isinstance(content, str):
                messages.append({"role": "user", "content": content})
            elif isinstance(content, list):
                non_tool = [b for b in content if not (isinstance(b, dict) and b.get("type") == "tool_result")]
                if non_tool:
                    oai_content, _ = _content_to_openai(non_tool)
                    if oai_content is not None:
                        messages.append({"role": "user", "content": oai_content})
        elif role == "assistant":
            oai_content, tool_calls = _content_to_openai(content)
            m: dict = {"role": "assistant"}
            m["content"] = oai_content
            if tool_calls:
                m["tool_calls"] = tool_calls
            messages.append(m)

    payload: dict = {
        "model": nim_model,
        "messages": messages,
        "max_tokens": body.get("max_tokens", 1024),
        "stream": bool(body.get("stream", False)),
    }
    if "temperature" in body:
        payload["temperature"] = body["temperature"]
    if "top_p" in body:
        payload["top_p"] = body["top_p"]
    if body.get("stop_sequences"):
        payload["stop"] = body["stop_sequences"]

    tools = body.get("tools")
    if tools:
        payload["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
                },
            }
            for t in tools
        ]
        tc = body.get("tool_choice")
        if tc:
            payload["tool_choice"] = _tool_choice_to_openai(tc)

    return payload


def _tool_choice_to_openai(tc: dict):
    t = tc.get("type")
    if t == "auto":
        return "auto"
    if t == "any":
        return "required"
    if t == "tool" and tc.get("name"):
        return {"type": "function", "function": {"name": tc["name"]}}
    return "auto"


_STOP_MAP = {
    "stop": "end_turn",
    "length": "max_tokens",
    "tool_calls": "tool_use",
    "content_filter": "end_turn",
    None: "end_turn",
}


def _map_stop(reason: Optional[str]) -> str:
    return _STOP_MAP.get(reason, "end_turn")


# ---------------------------------------------------------------------------
# OpenAI response  ->  Anthropic response (non-streaming)
# ---------------------------------------------------------------------------


def openai_to_anthropic(resp: dict, model: str) -> dict:
    choice = (resp.get("choices") or [{}])[0]
    message = choice.get("message", {})
    content_blocks: list[dict] = []

    text = message.get("content")
    if text:
        content_blocks.append({"type": "text", "text": text})

    for tc in message.get("tool_calls") or []:
        fn = tc.get("function", {})
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        content_blocks.append(
            {
                "type": "tool_use",
                "id": tc.get("id") or f"toolu_{uuid.uuid4().hex[:24]}",
                "name": fn.get("name"),
                "input": args,
            }
        )

    if not content_blocks:
        content_blocks.append({"type": "text", "text": ""})

    usage = resp.get("usage", {})
    return {
        "id": resp.get("id") or f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": content_blocks,
        "stop_reason": _map_stop(choice.get("finish_reason")),
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }


# ---------------------------------------------------------------------------
# OpenAI SSE stream  ->  Anthropic SSE stream
# ---------------------------------------------------------------------------


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def openai_stream_to_anthropic(
    lines: AsyncIterator[str], model: str, usage_sink: Optional[dict] = None
) -> AsyncIterator[str]:
    msg_id = f"msg_{uuid.uuid4().hex[:24]}"

    # message_start
    yield _sse(
        "message_start",
        {
            "type": "message_start",
            "message": {
                "id": msg_id,
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": 0, "output_tokens": 0},
            },
        },
    )

    text_block_open = False
    # tool state keyed by openai tool_calls index -> anthropic content index
    tool_blocks: dict[int, int] = {}
    next_index = 0
    finish_reason = None
    output_tokens = 0
    input_tokens = 0

    async for raw in lines:
        if not raw or not raw.startswith("data:"):
            continue
        data = raw[len("data:"):].strip()
        if data == "[DONE]":
            break
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue

        if chunk.get("usage"):
            input_tokens = chunk["usage"].get("prompt_tokens", input_tokens)
            output_tokens = chunk["usage"].get("completion_tokens", output_tokens)

        choice = (chunk.get("choices") or [{}])[0]
        delta = choice.get("delta", {})
        if choice.get("finish_reason"):
            finish_reason = choice["finish_reason"]

        # Text delta
        text = delta.get("content")
        if text:
            if not text_block_open:
                yield _sse(
                    "content_block_start",
                    {
                        "type": "content_block_start",
                        "index": next_index,
                        "content_block": {"type": "text", "text": ""},
                    },
                )
                text_block_open = True
                text_index = next_index
                next_index += 1
            yield _sse(
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": text_index,
                    "delta": {"type": "text_delta", "text": text},
                },
            )

        # Tool call deltas
        for tc in delta.get("tool_calls") or []:
            oai_idx = tc.get("index", 0)
            fn = tc.get("function", {})
            if oai_idx not in tool_blocks:
                # Close an open text block before starting a tool block.
                idx = next_index
                tool_blocks[oai_idx] = idx
                next_index += 1
                yield _sse(
                    "content_block_start",
                    {
                        "type": "content_block_start",
                        "index": idx,
                        "content_block": {
                            "type": "tool_use",
                            "id": tc.get("id") or f"toolu_{uuid.uuid4().hex[:24]}",
                            "name": fn.get("name") or "",
                            "input": {},
                        },
                    },
                )
            args_fragment = fn.get("arguments")
            if args_fragment:
                yield _sse(
                    "content_block_delta",
                    {
                        "type": "content_block_delta",
                        "index": tool_blocks[oai_idx],
                        "delta": {"type": "input_json_delta", "partial_json": args_fragment},
                    },
                )

    # Close any open blocks
    if text_block_open:
        yield _sse("content_block_stop", {"type": "content_block_stop", "index": text_index})
    for idx in tool_blocks.values():
        yield _sse("content_block_stop", {"type": "content_block_stop", "index": idx})

    yield _sse(
        "message_delta",
        {
            "type": "message_delta",
            "delta": {"stop_reason": _map_stop(finish_reason), "stop_sequence": None},
            "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
        },
    )
    yield _sse("message_stop", {"type": "message_stop"})

    if usage_sink is not None:
        usage_sink["input_tokens"] = input_tokens
        usage_sink["output_tokens"] = output_tokens
        usage_sink["stop_reason"] = _map_stop(finish_reason)


# ---------------------------------------------------------------------------
# Token estimate (best-effort; Claude Code falls back to local estimation)
# ---------------------------------------------------------------------------


def estimate_tokens(body: dict) -> int:
    chars = 0
    system_text = _system_to_text(body.get("system")) or ""
    chars += len(system_text)
    for msg in body.get("messages", []):
        content = msg.get("content")
        if isinstance(content, str):
            chars += len(content)
        elif isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "text":
                    chars += len(b.get("text", ""))
    return max(1, chars // 4)
