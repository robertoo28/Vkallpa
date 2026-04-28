from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from ..core.constants import ROLE_VKALLPA_ADMIN
from ..core.security import ACCESS_TOKEN_TYPE, REFRESH_TOKEN_TYPE
from ..core.settings import settings
from ..services.data_repository import DataRepository, ScopedDataRepository, get_repo
from .service import CurrentUserContext, get_current_user_context


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_data_repository() -> DataRepository:
    return get_repo()


def _invalid_token_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token",
    )


def _decode_token_payload(token: str, expected_type: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise _invalid_token_error() from exc

    if payload.get("type") != expected_type:
        raise _invalid_token_error()
    return payload


def _get_required_claim(payload: dict[str, Any], claim_name: str) -> str:
    value = payload.get(claim_name)
    if not isinstance(value, str) or not value:
        raise _invalid_token_error()
    return value


def _get_tenant_claim(payload: dict[str, Any]) -> str | None:
    if "tenant_id" not in payload:
        raise _invalid_token_error()
    value = payload["tenant_id"]
    if value is None or isinstance(value, str):
        return value
    raise _invalid_token_error()


def _build_user_from_payload(payload: dict[str, Any]) -> CurrentUserContext:
    subject = _get_required_claim(payload, "sub")
    token_user_id = _get_required_claim(payload, "user_id")
    token_role = _get_required_claim(payload, "role")
    token_tenant_id = _get_tenant_claim(payload)

    if token_user_id != subject:
        raise _invalid_token_error()

    current_user = get_current_user_context(subject)
    if token_role != current_user.role:
        raise _invalid_token_error()
    if token_tenant_id != current_user.company_tenant_id:
        raise _invalid_token_error()
    return current_user


def get_current_user_from_refresh_token(token: str) -> CurrentUserContext:
    """Validate a refresh token and return its active user context."""
    payload = _decode_token_payload(token, REFRESH_TOKEN_TYPE)
    return _build_user_from_payload(payload)


def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUserContext:
    payload = _decode_token_payload(token, ACCESS_TOKEN_TYPE)
    return _build_user_from_payload(payload)


def require_roles(*roles: str) -> Callable[..., CurrentUserContext]:
    def dependency(
        current_user: CurrentUserContext = Depends(get_current_user),
    ) -> CurrentUserContext:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden",
            )
        return current_user

    return dependency


def require_module_access(module_key: str) -> Callable[..., CurrentUserContext]:
    def dependency(
        current_user: CurrentUserContext = Depends(get_current_user),
    ) -> CurrentUserContext:
        if (
            current_user.role != ROLE_VKALLPA_ADMIN
            and module_key not in current_user.module_permissions
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden",
            )
        return current_user

    return dependency


def get_scoped_data_repository(
    current_user: CurrentUserContext = Depends(get_current_user),
    repo: DataRepository = Depends(get_data_repository),
) -> DataRepository | ScopedDataRepository:
    if current_user.role == ROLE_VKALLPA_ADMIN:
        return repo
    return ScopedDataRepository(repo, current_user.effective_building_ids or [])
