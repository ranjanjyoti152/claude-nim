from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app import db
from app.auth import current_user
from app.models import CreatedKey, CreateKeyRequest, KeyOut
from app.security import generate_key, hash_key, key_prefix, mask_key

router = APIRouter(prefix="/api/keys", tags=["keys"])


@router.post("", response_model=CreatedKey)
async def create_key(body: CreateKeyRequest, user: dict = Depends(current_user)):
    key = generate_key()
    now = datetime.now(timezone.utc)
    doc = {
        "label": body.label,
        "key_hash": hash_key(key),
        "prefix": key_prefix(key),
        "owner_id": user["_id"],
        "owner_email": user["email"],
        "revoked": False,
        "created_at": now,
    }
    result = await db.api_keys().insert_one(doc)
    return CreatedKey(
        id=str(result.inserted_id),
        label=body.label,
        key=key,
        prefix=doc["prefix"],
        created_at=now,
    )


@router.get("", response_model=list[KeyOut])
async def list_keys(user: dict = Depends(current_user)):
    # Admins see all keys; users see only their own.
    query = {} if user.get("role") == "admin" else {"owner_id": user["_id"]}
    out = []
    async for k in db.api_keys().find(query).sort("created_at", -1):
        out.append(
            KeyOut(
                id=str(k["_id"]),
                label=k["label"],
                prefix=k["prefix"],
                masked=mask_key(k["prefix"]),
                owner_email=k.get("owner_email"),
                created_at=k["created_at"],
                revoked=k.get("revoked", False),
            )
        )
    return out


@router.delete("/{key_id}")
async def revoke_key(key_id: str, user: dict = Depends(current_user)):
    query = {"_id": ObjectId(key_id)}
    if user.get("role") != "admin":
        query["owner_id"] = user["_id"]
    result = await db.api_keys().update_one(query, {"$set": {"revoked": True}})
    if result.matched_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Key not found")
    return {"ok": True}
