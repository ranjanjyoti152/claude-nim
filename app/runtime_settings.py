"""Runtime-editable settings, stored in Mongo, overriding .env defaults.

Provider config (NIM URL/key), caching, and backends can be changed from the
admin Settings page without restarting the container. Values fall back to the
.env-derived `settings` when unset."""
from app import db
from app.config import settings as env_settings

_DOC_ID = "gateway"
# Fields exposed on the Settings page and their env fallbacks.
_FIELDS = {
    "nim_base_url": lambda: env_settings.nim_base_url,
    "nvidia_api_key": lambda: env_settings.nvidia_api_key,
    "nim_backends": lambda: env_settings.nim_backends,
    "cache_enabled": lambda: env_settings.cache_enabled,
    "cache_ttl_seconds": lambda: env_settings.cache_ttl_seconds,
}


def _coll():
    return db.get_db()["settings"]


async def get_all() -> dict:
    doc = await _coll().find_one({"_id": _DOC_ID}) or {}
    out = {}
    for field, fallback in _FIELDS.items():
        out[field] = doc.get(field, fallback())
    return out


async def get(field: str):
    return (await get_all()).get(field)


async def update(values: dict) -> dict:
    clean = {k: v for k, v in values.items() if k in _FIELDS}
    if clean:
        await _coll().update_one({"_id": _DOC_ID}, {"$set": clean}, upsert=True)
    return await get_all()


async def masked() -> dict:
    """Settings for display — API key never returned in full."""
    data = await get_all()
    key = data.get("nvidia_api_key") or ""
    data["nvidia_api_key_set"] = bool(key)
    data["nvidia_api_key"] = (key[:8] + "…") if key else ""
    return data


def backends_from(data: dict) -> list[dict]:
    """Build the backend list from a runtime-settings dict (mirrors config.backends())."""
    out = [{"base_url": data["nim_base_url"], "api_key": data["nvidia_api_key"]}]
    for entry in (data.get("nim_backends") or "").split(","):
        entry = entry.strip()
        if not entry:
            continue
        url, _, key = entry.partition("|")
        out.append({"base_url": url.strip(), "api_key": key.strip()})
    return out
