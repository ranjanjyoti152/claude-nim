import hashlib
import secrets

from passlib.context import CryptContext

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

KEY_PREFIX = "sk-gw-"


# --- User passwords (bcrypt) ---
def hash_password(password: str) -> str:
    # bcrypt caps input at 72 bytes; truncate defensively.
    return _pwd.hash(password[:72])


def verify_password(password: str, hashed: str) -> bool:
    return _pwd.verify(password[:72], hashed)


# --- Gateway API keys (high-entropy random token, SHA-256 stored) ---
def generate_key() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(32)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def key_prefix(key: str) -> str:
    # Stored to help identify a key without revealing it.
    return key[: len(KEY_PREFIX) + 6]


def mask_key(prefix: str) -> str:
    return prefix + "…"
