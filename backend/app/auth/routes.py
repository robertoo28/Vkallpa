from fastapi import APIRouter, Depends

from ..core.security import create_token_pair
from .dependencies import get_current_user, get_current_user_from_refresh_token
from .schemas import (
    CurrentUserProfile,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RefreshRequest,
)
from .service import (
    CurrentUserContext,
    authenticate_user,
    build_current_user_profile,
    confirm_password_reset,
    request_password_reset,
)


router = APIRouter()


def _build_login_response(current_user: CurrentUserContext) -> LoginResponse:
    tokens = create_token_pair(
        current_user.user_id,
        current_user.company_tenant_id,
        current_user.role,
    )
    return LoginResponse(
        access_token=tokens.access_token,
        expires_in=tokens.access_expires_in,
        refresh_token=tokens.refresh_token,
        refresh_expires_in=tokens.refresh_expires_in,
        user=CurrentUserProfile.model_validate(
            build_current_user_profile(current_user)
        ),
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    current_user = authenticate_user(payload.identifier, payload.password)
    return _build_login_response(current_user)


@router.post("/refresh", response_model=LoginResponse)
def refresh(payload: RefreshRequest) -> LoginResponse:
    current_user = get_current_user_from_refresh_token(payload.refresh_token)
    return _build_login_response(current_user)


@router.post("/password-reset/request", response_model=MessageResponse)
def request_reset(payload: PasswordResetRequest) -> MessageResponse:
    """Queue a one-use password reset token for the requested email."""
    request_password_reset(payload.email)
    return MessageResponse(
        message="If the account exists, password reset instructions were sent."
    )


@router.post("/password-reset/confirm", response_model=MessageResponse)
def confirm_reset(payload: PasswordResetConfirmRequest) -> MessageResponse:
    """Confirm a password reset token and save the new password."""
    confirm_password_reset(payload.token, payload.password)
    return MessageResponse(message="Password updated successfully.")


@router.get("/me", response_model=CurrentUserProfile)
def me(
    current_user: CurrentUserContext = Depends(get_current_user),
) -> CurrentUserProfile:
    return CurrentUserProfile.model_validate(build_current_user_profile(current_user))
