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


async def resolve_model(claude_model: str) -> str:
    """Map an incoming Claude model string to a configured NIM model id.

    Resolution order: exact slot match -> 'default' mapping -> the string as-is
    (lets a user pass a raw NIM id straight through).
    """
    slot = _slot_for(claude_model)
    mapping = await db.model_mappings().find_one({"slot": slot})
    if mapping:
        return mapping["nim_model"]
    default = await db.model_mappings().find_one({"slot": "default"})
    if default:
        return default["nim_model"]
    return claude_model
