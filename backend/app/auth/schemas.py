from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from ..core.constants import (
    ALL_MODULE_KEYS,
    COMPANY_STATUS_VALUES,
    USER_ROLE_VALUES,
    USER_STATUS_VALUES,
)


class CompanyRef(BaseModel):
    id: str
    name: str
    slug: str
    status: str
    allowed_building_ids: list[str] = Field(default_factory=list)


class CurrentUserProfile(BaseModel):
    id: str
    username: str
    full_name: str
    role: str
    status: str
    company: CompanyRef | None = None
    module_permissions: list[str] = Field(default_factory=list)
    allowed_building_ids: list[str] = Field(default_factory=list)
    effective_building_ids: list[str] = Field(default_factory=list)
    can_manage_users: bool = False


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: CurrentUserProfile


class InitialAdminItem(BaseModel):
    id: str
    username: str
    full_name: str
    temporary_password: str | None = None


class CompanyItem(CompanyRef):
    tenant_id: str
    user_count: int = 0
    created_by_user_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    initial_admin: InitialAdminItem | None = None


class CompanyListResponse(BaseModel):
    items: list[CompanyItem]


class CreateCompanyRequest(BaseModel):
    tenant_id: str | None = None
    name: str
    slug: str | None = None
    status: str = "active"
    allowed_building_ids: list[str] = Field(default_factory=list)
    admin_username: str | None = None
    admin_full_name: str | None = None
    admin_password: str | None = Field(default=None, min_length=4)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in COMPANY_STATUS_VALUES:
            raise ValueError("Invalid company status")
        return value


class UpdateCompanyRequest(BaseModel):
    tenant_id: str | None = None
    name: str | None = None
    slug: str | None = None
    status: str | None = None
    allowed_building_ids: list[str] | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is not None and value not in COMPANY_STATUS_VALUES:
            raise ValueError("Invalid company status")
        return value


class UserItem(BaseModel):
    id: str
    username: str
    full_name: str
    role: str
    status: str
    company: CompanyRef | None = None
    module_permissions: list[str] = Field(default_factory=list)
    effective_module_permissions: list[str] = Field(default_factory=list)
    allowed_building_ids: list[str] = Field(default_factory=list)
    effective_building_ids: list[str] = Field(default_factory=list)
    created_by_user_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class UserListResponse(BaseModel):
    items: list[UserItem]


class CreateUserRequest(BaseModel):
    username: str
    full_name: str
    password: str = Field(min_length=4)
    role: str
    status: str = "active"
    company_id: str | None = None
    module_permissions: list[str] = Field(default_factory=list)
    allowed_building_ids: list[str] = Field(default_factory=list)

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in USER_ROLE_VALUES:
            raise ValueError("Invalid user role")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in USER_STATUS_VALUES:
            raise ValueError("Invalid user status")
        return value

    @field_validator("module_permissions")
    @classmethod
    def validate_modules(cls, value: list[str]) -> list[str]:
        invalid = [item for item in value if item not in ALL_MODULE_KEYS]
        if invalid:
            raise ValueError("Invalid module permissions")
        return value


class UpdateUserRequest(BaseModel):
    username: str | None = None
    full_name: str | None = None
    password: str | None = None
    role: str | None = None
    status: str | None = None
    company_id: str | None = None
    module_permissions: list[str] | None = None
    allowed_building_ids: list[str] | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str | None) -> str | None:
        if value is not None and value not in USER_ROLE_VALUES:
            raise ValueError("Invalid user role")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is not None and value not in USER_STATUS_VALUES:
            raise ValueError("Invalid user status")
        return value

    @field_validator("module_permissions")
    @classmethod
    def validate_modules(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        invalid = [item for item in value if item not in ALL_MODULE_KEYS]
        if invalid:
            raise ValueError("Invalid module permissions")
        return value
