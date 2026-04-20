from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import jwt
from passlib.context import CryptContext

from .settings import settings


ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    access_expires_in: int
    refresh_token: str
    refresh_expires_in: int


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


def _create_token(
    subject: str,
    token_type: str,
    expire_minutes: int,
    tenant_id: str | None,
    role: str,
) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expire_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "user_id": subject,
        "tenant_id": tenant_id,
        "role": role,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": expire,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expire_minutes * 60


def create_access_token(
    subject: str,
    tenant_id: str | None,
    role: str,
) -> tuple[str, int]:
    """Create a signed access token for the current authenticated user."""
    return _create_token(
        subject,
        ACCESS_TOKEN_TYPE,
        settings.jwt_expire_minutes,
        tenant_id,
        role,
    )


def create_refresh_token(
    subject: str,
    tenant_id: str | None,
    role: str,
) -> tuple[str, int]:
    """Create a signed refresh token for the current authenticated user."""
    return _create_token(
        subject,
        REFRESH_TOKEN_TYPE,
        settings.jwt_refresh_expire_minutes,
        tenant_id,
        role,
    )


def create_token_pair(subject: str, tenant_id: str | None, role: str) -> TokenPair:
    """Create the access and refresh JWTs for a login session."""
    access_token, access_expires_in = create_access_token(subject, tenant_id, role)
    refresh_token, refresh_expires_in = create_refresh_token(subject, tenant_id, role)
    return TokenPair(
        access_token=access_token,
        access_expires_in=access_expires_in,
        refresh_token=refresh_token,
        refresh_expires_in=refresh_expires_in,
    )
