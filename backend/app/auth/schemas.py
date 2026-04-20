from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..core.constants import (
    ALL_MODULE_KEYS,
    COMPANY_STATUS_VALUES,
    USER_ROLE_VALUES,
    USER_STATUS_VALUES,
)


class TenantGeneralConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timezone: str = "America/Guayaquil"
    language: Literal["es", "en", "fr"] = "es"
    currency: Literal["USD", "EUR", "COP", "PEN", "CLP"] = "USD"

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Timezone is required")
        return value


class TenantEnergyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tariff_per_kwh: float = Field(default=0.12, ge=0)
    carbon_factor_kg_per_kwh: float = Field(default=0.25, ge=0)
    energy_unit: Literal["kWh", "MWh"] = "kWh"


class TenantAlertsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    consumption_threshold_kwh: float = Field(default=5000, ge=0)
    anomaly_notifications: bool = True


class TenantReportsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_period: Literal["daily", "weekly", "monthly"] = "monthly"
    default_format: Literal["pdf", "excel"] = "pdf"
    include_carbon: bool = True


class TenantConfigItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    general: TenantGeneralConfig = Field(default_factory=TenantGeneralConfig)
    energy: TenantEnergyConfig = Field(default_factory=TenantEnergyConfig)
    alerts: TenantAlertsConfig = Field(default_factory=TenantAlertsConfig)
    reports: TenantReportsConfig = Field(default_factory=TenantReportsConfig)


class TenantGeneralConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timezone: str | None = None
    language: Literal["es", "en", "fr"] | None = None
    currency: Literal["USD", "EUR", "COP", "PEN", "CLP"] | None = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Timezone is required")
        return value


class TenantEnergyConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tariff_per_kwh: float | None = Field(default=None, ge=0)
    carbon_factor_kg_per_kwh: float | None = Field(default=None, ge=0)
    energy_unit: Literal["kWh", "MWh"] | None = None


class TenantAlertsConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    consumption_threshold_kwh: float | None = Field(default=None, ge=0)
    anomaly_notifications: bool | None = None


class TenantReportsConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_period: Literal["daily", "weekly", "monthly"] | None = None
    default_format: Literal["pdf", "excel"] | None = None
    include_carbon: bool | None = None


class TenantConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    general: TenantGeneralConfigUpdate | None = None
    energy: TenantEnergyConfigUpdate | None = None
    alerts: TenantAlertsConfigUpdate | None = None
    reports: TenantReportsConfigUpdate | None = None


class CompanyRef(BaseModel):
    id: str
    tenant_id: str
    name: str
    slug: str
    status: str
    allowed_building_ids: list[str] = Field(default_factory=list)
    config: TenantConfigItem = Field(default_factory=TenantConfigItem)


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
    username: str | None = None
    email: str | None = None
    password: str

    @model_validator(mode="after")
    def validate_identifier(self) -> "LoginRequest":
        username = self.username.strip() if self.username else None
        email = self.email.strip() if self.email else None
        if not username and not email:
            raise ValueError("Email is required")
        self.username = username
        self.email = email
        return self

    @property
    def identifier(self) -> str:
        return self.email or self.username or ""


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str
    refresh_expires_in: int
    user: CurrentUserProfile


class RefreshRequest(BaseModel):
    refresh_token: str


class InitialAdminItem(BaseModel):
    id: str
    username: str
    full_name: str
    temporary_password: str | None = None


class CompanyItem(CompanyRef):
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
