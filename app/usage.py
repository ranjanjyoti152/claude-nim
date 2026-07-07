from datetime import datetime, timezone

from app import db


async def record(
    owner: dict,
    claude_model: str,
    nim_model: str,
    input_tokens: int,
    output_tokens: int,
    streamed: bool,
    status: str = "ok",
) -> None:
    """Best-effort usage log; never raise into the request path."""
    try:
        await db.usage().insert_one(
            {
                "owner_id": owner.get("owner_id"),
                "owner_email": owner.get("owner_email"),
                "key_label": owner.get("label"),
                "claude_model": claude_model,
                "nim_model": nim_model,
                "input_tokens": int(input_tokens or 0),
                "output_tokens": int(output_tokens or 0),
                "streamed": streamed,
                "status": status,
                "created_at": datetime.now(timezone.utc),
            }
        )
    except Exception:
        pass
