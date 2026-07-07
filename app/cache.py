"""Response caching for identical non-streaming requests, backed by a Mongo
TTL collection. Keyed by a hash of the resolved NIM payload."""
import hashlib
import json
from datetime import datetime, timedelta, timezone

from app import db
from app.config import settings

_ttl_ensured = False


async def _ensure_ttl() -> None:
    global _ttl_ensured
    if _ttl_ensured:
        return
    # Mongo expires docs `cache_ttl_seconds` after `created_at`.
    await db.get_db()["response_cache"].create_index(
        "created_at", expireAfterSeconds=settings.cache_ttl_seconds
    )
    _ttl_ensured = True


def _coll():
    return db.get_db()["response_cache"]


def key_for(payload: dict, namespace: str = "anthropic") -> str:
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256((namespace + "\x00" + blob).encode()).hexdigest()


async def get(payload: dict, namespace: str = "anthropic") -> dict | None:
    if not settings.cache_enabled:
        return None
    await _ensure_ttl()
    doc = await _coll().find_one({"_id": key_for(payload, namespace)})
    if not doc:
        return None
    # Guard against a clock/TTL race: honor the ttl in-app too.
    age = datetime.now(timezone.utc) - doc["created_at"].replace(tzinfo=timezone.utc)
    if age > timedelta(seconds=settings.cache_ttl_seconds):
        return None
    return doc["response"]


async def put(payload: dict, response: dict, namespace: str = "anthropic") -> None:
    if not settings.cache_enabled:
        return
    await _ensure_ttl()
    await _coll().update_one(
        {"_id": key_for(payload, namespace)},
        {"$set": {"response": response, "created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
