"""Response caching for identical non-streaming requests, backed by a Mongo
TTL collection. Keyed by a hash of the resolved NIM payload."""
import hashlib
import json
from datetime import datetime, timedelta, timezone

from app import db, runtime_settings

_ttl_ensured = False


async def _ensure_ttl(ttl: int) -> None:
    global _ttl_ensured
    if _ttl_ensured:
        return
    # Mongo expires docs `ttl` seconds after `created_at`.
    await db.get_db()["response_cache"].create_index(
        "created_at", expireAfterSeconds=ttl
    )
    _ttl_ensured = True


def _coll():
    return db.get_db()["response_cache"]


def key_for(payload: dict, namespace: str = "anthropic") -> str:
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256((namespace + "\x00" + blob).encode()).hexdigest()


async def get(payload: dict, namespace: str = "anthropic") -> dict | None:
    cfg = await runtime_settings.get_all()
    if not cfg.get("cache_enabled"):
        return None
    await _ensure_ttl(int(cfg.get("cache_ttl_seconds", 300)))
    doc = await _coll().find_one({"_id": key_for(payload, namespace)})
    if not doc:
        return None
    # Guard against a clock/TTL race: honor the ttl in-app too.
    age = datetime.now(timezone.utc) - doc["created_at"].replace(tzinfo=timezone.utc)
    if age > timedelta(seconds=int(cfg.get("cache_ttl_seconds", 300))):
        return None
    return doc["response"]


async def put(payload: dict, response: dict, namespace: str = "anthropic") -> None:
    cfg = await runtime_settings.get_all()
    if not cfg.get("cache_enabled"):
        return
    await _ensure_ttl(int(cfg.get("cache_ttl_seconds", 300)))
    await _coll().update_one(
        {"_id": key_for(payload, namespace)},
        {"$set": {"response": response, "created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
