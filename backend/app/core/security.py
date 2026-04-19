from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt
from passlib.context import CryptContext

from .settings import settings


pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def ensure_password_hash(password_or_hash: str) -> str:
    if not password_or_hash:
        raise ValueError("Password seed value is required")
    if password_or_hash.startswith("plain:"):
        return hash_password(password_or_hash.split("plain:", 1)[1])
    if password_or_hash.startswith("$2"):
        return password_or_hash
    return hash_password(password_or_hash)


def verify_password(plain: str, hashed: str) -> bool:
    if hashed.startswith("plain:"):
        return plain == hashed.split("plain:", 1)[1]
    if hashed.startswith("$2"):
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str) -> tuple[str, int]:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, settings.jwt_expire_minutes * 60
