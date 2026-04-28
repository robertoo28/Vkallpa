from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DataSourceFieldMapping(BaseModel):
    """Column mapping used to normalize energy files."""

    model_config = ConfigDict(extra="forbid")

    timestamp: str = Field(min_length=1)
    energy_kwh: str = Field(min_length=1)
    power_kw: str | None = None
    site: str | None = None
    energy_type: str | None = None
    location: str | None = None

    @field_validator(
        "timestamp",
        "energy_kwh",
        "power_kw",
        "site",
        "energy_type",
        "location",
        mode="before",
    )
    @classmethod
    def normalize_column_name(cls, value: Any) -> Any:
        """Trim string column names and collapse empty optional values."""
        if value is None or not isinstance(value, str):
            return value
        stripped = value.strip()
        return stripped or None


class DataSourceConfigRequest(BaseModel):
    """Payload used to create or update a tenant data source."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str | None = None
    source_type: Literal["azure_blob"] = "azure_blob"
    name: str = Field(default="Azure Blob Storage", min_length=1)
    container_name: str = Field(min_length=1)
    blob_prefix: str | None = None
    default_sheet_name: str | None = None
    field_mapping: DataSourceFieldMapping

    @field_validator("name", "container_name", mode="before")
    @classmethod
    def strip_required_text(cls, value: Any) -> Any:
        """Trim required text values."""
        if not isinstance(value, str):
            return value
        return value.strip()

    @field_validator("tenant_id", "blob_prefix", "default_sheet_name", mode="before")
    @classmethod
    def strip_optional_text(cls, value: Any) -> Any:
        """Trim optional text values."""
        if value is None or not isinstance(value, str):
            return value
        stripped = value.strip()
        return stripped or None


class DataSourceConfigResponse(BaseModel):
    """Stored data source configuration for one tenant."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    tenant_id: str
    source_type: Literal["azure_blob"] = "azure_blob"
    name: str
    container_name: str
    blob_prefix: str | None = None
    default_sheet_name: str | None = None
    field_mapping: DataSourceFieldMapping
    created_at: str | None = None
    updated_at: str | None = None


class DataSourceFileItem(BaseModel):
    """File available in the configured Azure Blob container."""

    name: str
    format: Literal["csv", "xlsx"]


class DataSourceFilesResponse(BaseModel):
    """List of files available for a tenant data source."""

    items: list[DataSourceFileItem]


class DataSourceValidationError(BaseModel):
    """Specific validation error found while previewing a file."""

    field: str
    column: str | None = None
    message: str
    invalid_count: int | None = None


class DataSourcePreviewRequest(BaseModel):
    """Request used to preview and validate a CSV or Excel file."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str | None = None
    blob_name: str = Field(min_length=1)
    sheet_name: str | None = None
    field_mapping: DataSourceFieldMapping | None = None

    @field_validator("tenant_id", "blob_name", "sheet_name", mode="before")
    @classmethod
    def strip_text(cls, value: Any) -> Any:
        """Trim text values."""
        if value is None or not isinstance(value, str):
            return value
        stripped = value.strip()
        return stripped or None


class DataSourcePreviewResponse(BaseModel):
    """Preview rows and validation state for an energy file."""

    blob_name: str
    format: Literal["csv", "xlsx"]
    columns: list[str]
    rows: list[dict[str, Any]]
    validation_errors: list[DataSourceValidationError]
    is_valid: bool
