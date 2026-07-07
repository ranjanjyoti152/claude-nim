from app import db


def _slot_for(model: str) -> str:
    low = (model or "").lower()
    if "opus" in low:
        return "opus"
    if "haiku" in low:
        return "haiku"
    if "sonnet" in low:
        return "sonnet"
    return "default"


def _looks_like_nim_id(model: str) -> bool:
    """A raw NIM model id looks like 'vendor/model' — pass those through
    untouched instead of routing them to the 'default' slot."""
    m = model or ""
    return "/" in m and not m.lower().startswith("claude")


async def resolve_model(claude_model: str) -> str:
    """Map an incoming model string to a configured NIM model id.

    - A raw NIM id ('vendor/model') is passed through unchanged.
    - A Claude slot name (claude-opus/sonnet/haiku, or bare opus/sonnet/haiku)
      resolves via its slot mapping.
    - Anything else falls back to the 'default' mapping, then the string as-is.
    """
    if _looks_like_nim_id(claude_model):
        return claude_model
    slot = _slot_for(claude_model)
    mapping = await db.model_mappings().find_one({"slot": slot})
    if mapping:
        return mapping["nim_model"]
    default = await db.model_mappings().find_one({"slot": "default"})
    if default:
        return default["nim_model"]
    return claude_model
