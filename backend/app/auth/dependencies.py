from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from ..core.constants import ROLE_VKALLPA_ADMIN
from ..core.settings import settings
from ..services.data_repository import DataRepository, ScopedDataRepository, get_repo
from .service import CurrentUserContext, get_current_user_context


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_data_repository() -> DataRepository:
    return get_repo()


def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUserContext:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        subject = payload.get("sub")
        if not subject:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return get_current_user_context(subject)
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


def require_roles(*roles: str):
    def dependency(current_user: CurrentUserContext = Depends(get_current_user)) -> CurrentUserContext:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return current_user

    return dependency


def require_module_access(module_key: str):
    def dependency(current_user: CurrentUserContext = Depends(get_current_user)) -> CurrentUserContext:
        if current_user.role != ROLE_VKALLPA_ADMIN and module_key not in current_user.module_permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return current_user

    return dependency


def get_scoped_data_repository(
    current_user: CurrentUserContext = Depends(get_current_user),
    repo: DataRepository = Depends(get_data_repository),
) -> DataRepository | ScopedDataRepository:
    if current_user.role == ROLE_VKALLPA_ADMIN:
        return repo
    return ScopedDataRepository(repo, current_user.effective_building_ids or [])
