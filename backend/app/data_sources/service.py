from __future__ import annotations

from datetime import datetime, timezone
import io
from pathlib import PurePosixPath
from typing import Any, Literal

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status
import pandas as pd

from ..auth.service import CurrentUserContext
from ..core.constants import ROLE_COMPANY_ADMIN, ROLE_VKALLPA_ADMIN
from ..core.mongo import (
    get_audit_logs_collection,
    get_companies_collection,
    get_data_sources_collection,
    serialize_mongo_id,
)
from ..services.data_repository import AzureDataError, DataRepository
from .schemas import (
    DataSourceConfigRequest,
    DataSourceFieldMapping,
    DataSourcePreviewRequest,
)

DataSourceFormat = Literal["csv", "xlsx"]

DEFAULT_FIELD_MAPPING = DataSourceFieldMapping(
    timestamp="Date",
    energy_kwh="Energie_periode_kWh",
    power_kw="Puissance_moyenne_kW",
    site="Batiment",
)
SUPPORTED_FILE_FORMATS: dict[str, DataSourceFormat] = {
    ".csv": "csv",
    ".xlsx": "xlsx",
}
NUMERIC_FIELDS = {"energy_kwh", "power_kw"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _parse_object_id(value: str) -> ObjectId | None:
    try:
        return ObjectId(value)
    except InvalidId:
        return None


def _get_company_by_identifier(identifier: str) -> dict | None:
    companies = get_companies_collection()
    object_id = _parse_object_id(identifier)
    if object_id is not None:
        company = companies.find_one({"_id": object_id})
        if company is not None:
            return company
    return companies.find_one({"tenant_id": identifier})


def _get_file_format(blob_name: str) -> DataSourceFormat:
    suffix = PurePosixPath(blob_name).suffix.lower()
    file_format = SUPPORTED_FILE_FORMATS.get(suffix)
    if file_format is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV and XLSX files are supported",
        )
    return file_format


def _assert_tenant_admin(actor: CurrentUserContext) -> None:
    if actor.role in {ROLE_VKALLPA_ADMIN, ROLE_COMPANY_ADMIN}:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def resolve_tenant_id(
    actor: CurrentUserContext,
    requested_tenant_id: str | None,
) -> str:
    """Resolve and authorize the tenant used by a data source operation."""
    _assert_tenant_admin(actor)
    if actor.role == ROLE_COMPANY_ADMIN:
        actor_tenant_id = actor.company_tenant_id
        if actor_tenant_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current user is not associated with a tenant",
            )
        if requested_tenant_id in {None, actor_tenant_id, actor.company_id}:
            return actor_tenant_id
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    if not requested_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tenant_id is required",
        )
    company = _get_company_by_identifier(requested_tenant_id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    return company.get("tenant_id") or company["slug"]


def _record_audit_log(
    actor: CurrentUserContext,
    tenant_id: str,
    action: str,
    details: dict[str, Any],
) -> None:
    actor_id = _parse_object_id(actor.user_id)
    get_audit_logs_collection().insert_one(
        {
            "tenant_id": tenant_id,
            "action": action,
            "target_id": tenant_id,
            "actor_user_id": actor_id,
            "details": details,
            "created_at": _utcnow(),
        }
    )


def _serialize_config(doc: dict[str, Any] | None, tenant_id: str) -> dict[str, Any]:
    if doc is None:
        return {
            "id": None,
            "tenant_id": tenant_id,
            "source_type": "azure_blob",
            "name": "Azure Blob Storage",
            "container_name": "",
            "blob_prefix": None,
            "default_sheet_name": None,
            "field_mapping": DEFAULT_FIELD_MAPPING,
            "created_at": None,
            "updated_at": None,
        }
    return {
        "id": serialize_mongo_id(doc.get("_id")),
        "tenant_id": doc["tenant_id"],
        "source_type": doc.get("source_type", "azure_blob"),
        "name": doc["name"],
        "container_name": doc["container_name"],
        "blob_prefix": doc.get("blob_prefix"),
        "default_sheet_name": doc.get("default_sheet_name"),
        "field_mapping": doc.get("field_mapping") or DEFAULT_FIELD_MAPPING.model_dump(),
        "created_at": _serialize_datetime(doc.get("created_at")),
        "updated_at": _serialize_datetime(doc.get("updated_at")),
    }


def get_data_source_config(
    actor: CurrentUserContext,
    tenant_id: str | None,
) -> dict[str, Any]:
    """Return the stored source configuration for one tenant."""
    resolved_tenant_id = resolve_tenant_id(actor, tenant_id)
    doc = get_data_sources_collection().find_one({"tenant_id": resolved_tenant_id})
    return _serialize_config(doc, resolved_tenant_id)


def save_data_source_config(
    actor: CurrentUserContext,
    payload: DataSourceConfigRequest,
) -> dict[str, Any]:
    """Create or update a tenant data source configuration."""
    resolved_tenant_id = resolve_tenant_id(actor, payload.tenant_id)
    data_sources = get_data_sources_collection()
    now = _utcnow()
    existing = data_sources.find_one({"tenant_id": resolved_tenant_id})
    update_doc = {
        "tenant_id": resolved_tenant_id,
        "source_type": payload.source_type,
        "name": payload.name,
        "container_name": payload.container_name,
        "blob_prefix": payload.blob_prefix,
        "default_sheet_name": payload.default_sheet_name,
        "field_mapping": payload.field_mapping.model_dump(),
        "updated_at": now,
    }
    if existing is None:
        update_doc["created_at"] = now
        data_sources.insert_one(update_doc)
    else:
        data_sources.update_one(
            {"_id": existing["_id"]},
            {"$set": update_doc},
        )

    _record_audit_log(
        actor,
        resolved_tenant_id,
        "data_source.config_updated",
        {
            "source_type": payload.source_type,
            "container_name": payload.container_name,
            "blob_prefix": payload.blob_prefix,
        },
    )
    saved = data_sources.find_one({"tenant_id": resolved_tenant_id})
    return _serialize_config(saved, resolved_tenant_id)


def list_data_source_files(
    actor: CurrentUserContext,
    tenant_id: str | None,
    repo: DataRepository,
) -> dict[str, Any]:
    """List CSV and XLSX files available for a tenant data source."""
    resolved_tenant_id = resolve_tenant_id(actor, tenant_id)
    config = get_data_sources_collection().find_one({"tenant_id": resolved_tenant_id})
    blob_prefix = (config or {}).get("blob_prefix") or ""

    try:
        blob_names = repo.list_blobs()
    except AzureDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Azure error",
        ) from exc

    items = []
    for blob_name in sorted(blob_names):
        if blob_prefix and not blob_name.startswith(blob_prefix):
            continue
        suffix = PurePosixPath(blob_name).suffix.lower()
        file_format = SUPPORTED_FILE_FORMATS.get(suffix)
        if file_format is not None:
            items.append({"name": blob_name, "format": file_format})
    return {"items": items}


def _read_dataframe(
    data: bytes,
    file_format: DataSourceFormat,
    sheet_name: str | None,
) -> pd.DataFrame:
    try:
        if file_format == "csv":
            return pd.read_csv(io.BytesIO(data))
        return pd.read_excel(
            io.BytesIO(data),
            sheet_name=sheet_name or 0,
            engine="openpyxl",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to read file: {exc}",
        ) from exc


def _clean_cell(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def _build_preview_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    rows = df.head(5).to_dict(orient="records")
    return [
        {str(column): _clean_cell(value) for column, value in row.items()}
        for row in rows
    ]


def _validate_column_presence(
    columns: set[str],
    mapping: dict[str, str | None],
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for field, column in mapping.items():
        if column is None:
            continue
        if column not in columns:
            errors.append(
                {
                    "field": field,
                    "column": column,
                    "message": "Mapped column was not found in the file",
                    "invalid_count": None,
                }
            )
    return errors


def _validate_duplicate_mapping(
    mapping: dict[str, str | None],
) -> list[dict[str, Any]]:
    seen: dict[str, str] = {}
    errors: list[dict[str, Any]] = []
    for field, column in mapping.items():
        if column is None:
            continue
        if column in seen:
            errors.append(
                {
                    "field": field,
                    "column": column,
                    "message": f"Column already mapped to {seen[column]}",
                    "invalid_count": None,
                }
            )
        seen[column] = field
    return errors


def _validate_column_values(
    df: pd.DataFrame,
    mapping: dict[str, str | None],
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    if df.empty:
        errors.append(
            {
                "field": "file",
                "column": None,
                "message": "File has no data rows",
                "invalid_count": None,
            }
        )
        return errors

    timestamp_column = mapping.get("timestamp")
    if timestamp_column is not None and timestamp_column in df.columns:
        series = df[timestamp_column].dropna()
        invalid_count = int(pd.to_datetime(series, errors="coerce").isna().sum())
        if invalid_count:
            errors.append(
                {
                    "field": "timestamp",
                    "column": timestamp_column,
                    "message": "Timestamp column contains invalid dates",
                    "invalid_count": invalid_count,
                }
            )

    for field in NUMERIC_FIELDS:
        column = mapping.get(field)
        if column is None or column not in df.columns:
            continue
        series = df[column].dropna()
        invalid_count = int(pd.to_numeric(series, errors="coerce").isna().sum())
        if invalid_count:
            errors.append(
                {
                    "field": field,
                    "column": column,
                    "message": "Numeric column contains invalid values",
                    "invalid_count": invalid_count,
                }
            )
    return errors


def _validate_mapping(
    df: pd.DataFrame,
    mapping: DataSourceFieldMapping,
) -> list[dict[str, Any]]:
    raw_mapping = mapping.model_dump()
    errors = _validate_duplicate_mapping(raw_mapping)
    errors.extend(_validate_column_presence(set(df.columns), raw_mapping))
    errors.extend(_validate_column_values(df, raw_mapping))
    return errors


def _resolve_preview_mapping(
    tenant_id: str,
    payload_mapping: DataSourceFieldMapping | None,
) -> DataSourceFieldMapping:
    if payload_mapping is not None:
        return payload_mapping
    config = get_data_sources_collection().find_one({"tenant_id": tenant_id})
    if config and config.get("field_mapping"):
        return DataSourceFieldMapping.model_validate(config["field_mapping"])
    return DEFAULT_FIELD_MAPPING


def preview_data_source_file(
    actor: CurrentUserContext,
    payload: DataSourcePreviewRequest,
    repo: DataRepository,
) -> dict[str, Any]:
    """Read a sample from a CSV or XLSX file and return validation errors."""
    tenant_id = resolve_tenant_id(actor, payload.tenant_id)
    file_format = _get_file_format(payload.blob_name)
    mapping = _resolve_preview_mapping(tenant_id, payload.field_mapping)

    try:
        data = repo.download_blob_bytes(payload.blob_name)
    except AzureDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Azure error",
        ) from exc

    df = _read_dataframe(data, file_format, payload.sheet_name)
    df.columns = [str(column) for column in df.columns]
    validation_errors = _validate_mapping(df, mapping)
    return {
        "blob_name": payload.blob_name,
        "format": file_format,
        "columns": list(df.columns),
        "rows": _build_preview_rows(df),
        "validation_errors": validation_errors,
        "is_valid": len(validation_errors) == 0,
    }
