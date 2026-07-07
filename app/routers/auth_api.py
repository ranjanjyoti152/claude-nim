from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError

from app import db
from app.auth import create_access_token, current_user, require_admin
from app.models import LoginRequest, SignupRequest, TokenResponse, UserOut
from app.security import hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse)
async def signup(body: SignupRequest):
    # First user to register becomes admin.
    is_first = await db.users().count_documents({}) == 0
    role = "admin" if is_first else "user"
    doc = {
        "email": body.email.lower(),
        "password_hash": hash_password(body.password),
        "role": role,
        "created_at": datetime.now(timezone.utc),
    }
    try:
        result = await db.users().insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    uid = str(result.inserted_id)
    token = create_access_token(uid, doc["email"], role)
    return TokenResponse(access_token=token, role=role, email=doc["email"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    user = await db.users().find_one({"email": body.email.lower()})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    token = create_access_token(str(user["_id"]), user["email"], user["role"])
    return TokenResponse(access_token=token, role=user["role"], email=user["email"])


@router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(current_user)):
    return UserOut(
        id=str(user["_id"]),
        email=user["email"],
        role=user["role"],
        created_at=user["created_at"],
    )


@router.get("/users", response_model=list[UserOut])
async def list_users(_: dict = Depends(require_admin)):
    out = []
    async for u in db.users().find().sort("created_at", 1):
        out.append(
            UserOut(id=str(u["_id"]), email=u["email"], role=u["role"], created_at=u["created_at"])
        )
    return out


async def _admin_count() -> int:
    return await db.users().count_documents({"role": "admin"})


@router.put("/users/{user_id}/role")
async def set_role(user_id: str, body: dict, admin: dict = Depends(require_admin)):
    role = (body or {}).get("role")
    if role not in ("admin", "user"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "role must be 'admin' or 'user'")
    target = await db.users().find_one({"_id": ObjectId(user_id)})
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    # Don't allow demoting the last admin.
    if target["role"] == "admin" and role == "user" and await _admin_count() <= 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot demote the last admin")
    await db.users().update_one({"_id": ObjectId(user_id)}, {"$set": {"role": role}})
    return {"ok": True}


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: dict = Depends(require_admin)):
    if str(admin["_id"]) == user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You can't delete your own account")
    target = await db.users().find_one({"_id": ObjectId(user_id)})
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if target["role"] == "admin" and await _admin_count() <= 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot delete the last admin")
    # Revoke the user's gateway keys, then delete the account.
    await db.api_keys().update_many({"owner_id": target["_id"]}, {"$set": {"revoked": True}})
    await db.users().delete_one({"_id": target["_id"]})
    return {"ok": True}
