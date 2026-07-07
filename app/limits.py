"""Per-key rate limiting (requests/minute) and spend caps (total tokens).

Enforced against the usage collection so it works across gateway restarts and
multiple workers without extra infrastructure."""
from datetime import datetime, timedelta, timezone

from app import db


async def check(owner: dict) -> tuple[bool, str]:
    """Return (allowed, reason). owner is the api_keys document."""
    key_id = owner.get("_id")
    if key_id is None:
        return True, ""

    rpm = owner.get("rpm_limit") or 0          # 0 = unlimited
    token_cap = owner.get("token_cap") or 0    # 0 = unlimited

    if rpm > 0:
        since = datetime.now(timezone.utc) - timedelta(seconds=60)
        recent = await db.usage().count_documents(
            {"key_id": key_id, "created_at": {"$gte": since}}
        )
        if recent >= rpm:
            return False, f"Rate limit exceeded: {rpm} requests/minute"

    if token_cap > 0:
        agg = await db.usage().aggregate([
            {"$match": {"key_id": key_id}},
            {"$group": {"_id": None,
                        "total": {"$sum": {"$add": ["$input_tokens", "$output_tokens"]}}}},
        ]).to_list(1)
        used = agg[0]["total"] if agg else 0
        if used >= token_cap:
            return False, f"Token spend cap reached: {token_cap} tokens"

    return True, ""
