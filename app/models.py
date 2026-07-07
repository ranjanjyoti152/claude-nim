from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


# --- Auth payloads ---
class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    email: str


class UserOut(BaseModel):
    id: str
    email: str
    role: str
    created_at: datetime


# --- API keys ---
class CreateKeyRequest(BaseModel):
    label: str = Field(default="default", max_length=64)


class CreatedKey(BaseModel):
    id: str
    label: str
    key: str  # full plaintext, shown once
    prefix: str
    created_at: datetime


class KeyOut(BaseModel):
    id: str
    label: str
    prefix: str
    masked: str
    owner_email: Optional[str] = None
    created_at: datetime
    revoked: bool = False


# --- Model mappings ---
Slot = Literal["opus", "sonnet", "haiku", "default"]


class ModelMappingIn(BaseModel):
    slot: Slot
    nim_model: str


class ModelMappingOut(BaseModel):
    slot: str
    nim_model: str
