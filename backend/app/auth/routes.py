from fastapi import APIRouter, Depends

from ..core.security import create_access_token
from .dependencies import get_current_user
from .schemas import CurrentUserProfile, LoginRequest, LoginResponse
from .service import CurrentUserContext, authenticate_user, build_current_user_profile


router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    current_user = authenticate_user(payload.username, payload.password)
    token, expires_in = create_access_token(current_user.user_id)
    return LoginResponse(
        access_token=token,
        expires_in=expires_in,
        user=CurrentUserProfile.model_validate(build_current_user_profile(current_user)),
    )


@router.get("/me", response_model=CurrentUserProfile)
def me(current_user: CurrentUserContext = Depends(get_current_user)) -> CurrentUserProfile:
    return CurrentUserProfile.model_validate(build_current_user_profile(current_user))
