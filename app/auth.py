from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId
from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt

from app import db
from app.config import settings
from app.security import hash_key


# --- JWT ---
def create_access_token(user_id: str, email: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": user_id, "email": email, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _decode(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")


async def current_user(authorization: Optional[str] = Header(None)) -> dict:
    """Dashboard auth: JWT bearer token from the SPA."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    payload = _decode(authorization.split(" ", 1)[1])
    user = await db.users().find_one({"_id": ObjectId(payload["sub"])})
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


async def require_admin(user: dict = Depends(current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return user


# --- Gateway API-key auth (used by Claude Code requests) ---
def _extract_gateway_key(authorization: Optional[str], x_api_key: Optional[str]) -> Optional[str]:
    if x_api_key:
        return x_api_key
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1]
    return None


async def gateway_key_owner(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
) -> dict:
    """Validate an incoming gateway key (Authorization: Bearer or x-api-key)."""
    key = _extract_gateway_key(authorization, x_api_key)
    if not key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing API key")
    record = await db.api_keys().find_one({"key_hash": hash_key(key), "revoked": False})
    if not record:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")
    return record
