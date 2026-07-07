from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

from app import db
from app.auth import current_user

router = APIRouter(prefix="/api/usage", tags=["usage"])


def _scope(user: dict) -> dict:
    # Admins see all usage; users see only their own.
    return {} if user.get("role") == "admin" else {"owner_id": user["_id"]}


@router.get("/summary")
async def summary(user: dict = Depends(current_user)):
    match = _scope(user)
    since = datetime.now(timezone.utc) - timedelta(days=1)

    totals = await db.usage().aggregate([
        {"$match": match},
        {"$group": {
            "_id": None,
            "requests": {"$sum": 1},
            "input_tokens": {"$sum": "$input_tokens"},
            "output_tokens": {"$sum": "$output_tokens"},
        }},
    ]).to_list(1)
    t = totals[0] if totals else {"requests": 0, "input_tokens": 0, "output_tokens": 0}

    today = await db.usage().count_documents({**match, "created_at": {"$gte": since}})

    by_model = await db.usage().aggregate([
        {"$match": match},
        {"$group": {
            "_id": "$nim_model",
            "requests": {"$sum": 1},
            "input_tokens": {"$sum": "$input_tokens"},
            "output_tokens": {"$sum": "$output_tokens"},
        }},
        {"$sort": {"requests": -1}},
        {"$limit": 20},
    ]).to_list(20)

    return {
        "requests": t["requests"],
        "input_tokens": t["input_tokens"],
        "output_tokens": t["output_tokens"],
        "requests_last_24h": today,
        "by_model": [
            {
                "nim_model": m["_id"],
                "requests": m["requests"],
                "input_tokens": m["input_tokens"],
                "output_tokens": m["output_tokens"],
            }
            for m in by_model
        ],
    }


@router.get("/recent")
async def recent(user: dict = Depends(current_user), limit: int = 50):
    limit = max(1, min(limit, 200))
    out = []
    async for r in db.usage().find(_scope(user)).sort("created_at", -1).limit(limit):
        out.append({
            "created_at": r["created_at"],
            "owner_email": r.get("owner_email"),
            "claude_model": r.get("claude_model"),
            "nim_model": r.get("nim_model"),
            "input_tokens": r.get("input_tokens", 0),
            "output_tokens": r.get("output_tokens", 0),
            "streamed": r.get("streamed", False),
            "status": r.get("status", "ok"),
        })
    return out
