import httpx
from fastapi import APIRouter, Depends

from app import nim_client, runtime_settings
from app.auth import current_user, require_admin

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
async def get_settings(_: dict = Depends(current_user)):
    # Any logged-in user can view (key is masked); only admin can edit.
    return await runtime_settings.masked()


@router.put("")
async def update_settings(body: dict, _: dict = Depends(require_admin)):
    values = {}
    for f in ("nim_base_url", "nim_backends"):
        if f in body and body[f] is not None:
            values[f] = str(body[f]).strip()
    if "cache_enabled" in body:
        values["cache_enabled"] = bool(body["cache_enabled"])
    if "cache_ttl_seconds" in body and body["cache_ttl_seconds"] is not None:
        values["cache_ttl_seconds"] = max(0, int(body["cache_ttl_seconds"]))
    # Only overwrite the API key when a non-empty, non-masked value is sent.
    key = body.get("nvidia_api_key")
    if key and "…" not in key:
        values["nvidia_api_key"] = key.strip()
    await runtime_settings.update(values)
    return await runtime_settings.masked()


@router.post("/test-connection")
async def test_connection(_: dict = Depends(require_admin)):
    """Verify the current provider config can reach NIM and list models."""
    try:
        models = await nim_client.list_models()
        return {"ok": True, "model_count": len(models)}
    except httpx.HTTPStatusError as e:
        return {"ok": False, "status": e.response.status_code, "detail": e.response.text[:200]}
    except httpx.HTTPError as e:
        return {"ok": False, "status": 0, "detail": str(e)}
