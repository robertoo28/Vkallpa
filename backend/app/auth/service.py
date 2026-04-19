from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from secrets import token_urlsafe
import unicodedata

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from ..core.constants import (
    BUSINESS_MODULE_KEYS,
    COMPANY_ADMIN_MODULE_KEYS,
    COMPANY_STATUS_ACTIVE,
    COMPANY_STATUS_INACTIVE,
    DEFAULT_COMPANY_USER_MODULE_KEYS,
    ROLE_COMPANY_ADMIN,
    ROLE_COMPANY_USER,
    ROLE_VKALLPA_ADMIN,
    USER_STATUS_ACTIVE,
    VKALLPA_ADMIN_MODULE_KEYS,
)
from ..core.mongo import (
    get_audit_logs_collection,
    get_companies_collection,
    get_users_collection,
    serialize_mongo_id,
)
from ..core.security import hash_password, verify_password
from ..services.data_repository import AzureDataError, DataRepository


@dataclass(frozen=True)
class CurrentUserContext:
    user_id: str
    username: str
    full_name: str
    role: str
    status: str
    company_id: str | None
    company_name: str | None
    company_slug: str | None
    company_status: str | None
    module_permissions: list[str]
    effective_building_ids: list[str] | None
    company_allowed_building_ids: list[str]
    user_allowed_building_ids: list[str]
    created_by_user_id: str | None

    @property
    def can_manage_users(self) -> bool:
        return self.role in {ROLE_VKALLPA_ADMIN, ROLE_COMPANY_ADMIN}

    def has_module_access(self, module_key: str) -> bool:
        return self.role == ROLE_VKALLPA_ADMIN or module_key in self.module_permissions


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _normalize_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_value = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value.strip().lower())
    return ascii_value.strip("-")


def _normalize_tenant_id(value: str) -> str:
    tenant_id = _normalize_slug(value)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tenant_id",
        )
    return tenant_id


def _parse_object_id(value: str, label: str) -> ObjectId:
    try:
        return ObjectId(value)
    except InvalidId as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {label}",
        ) from exc


def _dedupe_preserve_order(values: list[str] | None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _resolve_company(company_id: str | None):
    if not company_id:
        return None
    companies = get_companies_collection()
    company = companies.find_one(
        {"_id": _parse_object_id(company_id, "company_id")}
    )
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )
    return company


def _find_company_by_identifier(identifier: str) -> dict | None:
    companies = get_companies_collection()
    try:
        company = companies.find_one({"_id": ObjectId(identifier)})
    except InvalidId:
        company = None
    if company:
        return company
    return companies.find_one({"tenant_id": identifier})


def _get_user_or_404(user_id: str):
    users = get_users_collection()
    user = users.find_one(
        {"_id": _parse_object_id(user_id, "user_id"), "deleted_at": None}
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


def _get_company_or_404(company_id: str):
    company = _find_company_by_identifier(company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )
    return company


def _company_is_active(company_doc: dict | None) -> bool:
    if company_doc is None:
        return True
    return company_doc.get("status") == COMPANY_STATUS_ACTIVE


def _build_effective_module_permissions(user_doc: dict) -> list[str]:
    role = user_doc["role"]
    if role == ROLE_VKALLPA_ADMIN:
        return VKALLPA_ADMIN_MODULE_KEYS
    if role == ROLE_COMPANY_ADMIN:
        return COMPANY_ADMIN_MODULE_KEYS
    requested = [
        item
        for item in user_doc.get("module_permissions", [])
        if item in BUSINESS_MODULE_KEYS
    ]
    return _dedupe_preserve_order(requested)


def _build_effective_buildings(
    user_doc: dict,
    company_doc: dict | None,
) -> list[str] | None:
    if user_doc["role"] == ROLE_VKALLPA_ADMIN:
        return None
    company_allowed = _dedupe_preserve_order(
        (company_doc or {}).get("allowed_building_ids", [])
    )
    user_allowed = _dedupe_preserve_order(user_doc.get("allowed_building_ids", []))
    if not company_allowed:
        return []
    if not user_allowed:
        return company_allowed
    company_allowed_set = set(company_allowed)
    return [item for item in user_allowed if item in company_allowed_set]


def _build_current_user_context(
    user_doc: dict,
    company_doc: dict | None,
) -> CurrentUserContext:
    return CurrentUserContext(
        user_id=serialize_mongo_id(user_doc["_id"]) or "",
        username=user_doc["username"],
        full_name=user_doc.get("full_name") or user_doc["username"],
        role=user_doc["role"],
        status=user_doc["status"],
        company_id=serialize_mongo_id(user_doc.get("company_id")),
        company_name=(company_doc or {}).get("name"),
        company_slug=(company_doc or {}).get("slug"),
        company_status=(company_doc or {}).get("status"),
        module_permissions=_build_effective_module_permissions(user_doc),
        effective_building_ids=_build_effective_buildings(user_doc, company_doc),
        company_allowed_building_ids=_dedupe_preserve_order(
            (company_doc or {}).get("allowed_building_ids", [])
        ),
        user_allowed_building_ids=_dedupe_preserve_order(
            user_doc.get("allowed_building_ids", [])
        ),
        created_by_user_id=serialize_mongo_id(user_doc.get("created_by_user_id")),
    )


def _assert_user_login_allowed(user_doc: dict, company_doc: dict | None) -> None:
    if (
        user_doc.get("deleted_at") is not None
        or user_doc.get("status") != USER_STATUS_ACTIVE
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if user_doc["role"] != ROLE_VKALLPA_ADMIN and not _company_is_active(company_doc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )


def authenticate_user(username: str, password: str) -> CurrentUserContext:
    users = get_users_collection()
    user_doc = users.find_one({"username": username, "deleted_at": None})
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    company_doc = None
    if user_doc.get("company_id"):
        company_doc = _resolve_company(serialize_mongo_id(user_doc.get("company_id")))
    _assert_user_login_allowed(user_doc, company_doc)

    if not verify_password(password, user_doc["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    return _build_current_user_context(user_doc, company_doc)


def get_current_user_context(user_id: str) -> CurrentUserContext:
    users = get_users_collection()
    user_doc = users.find_one(
        {"_id": _parse_object_id(user_id, "token subject"), "deleted_at": None}
    )
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    company_doc = None
    if user_doc.get("company_id"):
        company_doc = _resolve_company(serialize_mongo_id(user_doc.get("company_id")))
    if user_doc.get("status") != USER_STATUS_ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    if user_doc["role"] != ROLE_VKALLPA_ADMIN and not _company_is_active(company_doc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    return _build_current_user_context(user_doc, company_doc)


def build_current_user_profile(context: CurrentUserContext) -> dict:
    company_payload = None
    if context.company_id:
        company_payload = {
            "id": context.company_id,
            "name": context.company_name or "",
            "slug": context.company_slug or "",
            "status": context.company_status or COMPANY_STATUS_INACTIVE,
            "allowed_building_ids": context.company_allowed_building_ids,
        }

    return {
        "id": context.user_id,
        "username": context.username,
        "full_name": context.full_name,
        "role": context.role,
        "status": context.status,
        "company": company_payload,
        "module_permissions": context.module_permissions,
        "allowed_building_ids": (
            context.user_allowed_building_ids or context.company_allowed_building_ids
        ),
        "effective_building_ids": context.effective_building_ids or [],
        "can_manage_users": context.can_manage_users,
    }


def _serialize_company(
    company_doc: dict,
    user_count: int = 0,
    initial_admin: dict | None = None,
) -> dict:
    return {
        "id": serialize_mongo_id(company_doc["_id"]),
        "tenant_id": company_doc.get("tenant_id") or company_doc["slug"],
        "name": company_doc["name"],
        "slug": company_doc["slug"],
        "status": company_doc["status"],
        "allowed_building_ids": _dedupe_preserve_order(
            company_doc.get("allowed_building_ids", [])
        ),
        "user_count": user_count,
        "created_by_user_id": serialize_mongo_id(company_doc.get("created_by_user_id")),
        "created_at": _serialize_datetime(company_doc.get("created_at")),
        "updated_at": _serialize_datetime(company_doc.get("updated_at")),
        "initial_admin": initial_admin,
    }


def _serialize_user(user_doc: dict, company_doc: dict | None) -> dict:
    context = _build_current_user_context(user_doc, company_doc)
    company_payload = None
    if company_doc:
        company_payload = {
            "id": serialize_mongo_id(company_doc["_id"]),
            "name": company_doc["name"],
            "slug": company_doc["slug"],
            "status": company_doc["status"],
            "allowed_building_ids": _dedupe_preserve_order(
                company_doc.get("allowed_building_ids", [])
            ),
        }
    return {
        "id": context.user_id,
        "username": context.username,
        "full_name": context.full_name,
        "role": context.role,
        "status": context.status,
        "company": company_payload,
        "module_permissions": _dedupe_preserve_order(
            user_doc.get("module_permissions", [])
        ),
        "effective_module_permissions": context.module_permissions,
        "allowed_building_ids": _dedupe_preserve_order(
            user_doc.get("allowed_building_ids", [])
        ),
        "effective_building_ids": context.effective_building_ids or [],
        "created_by_user_id": context.created_by_user_id,
        "created_at": _serialize_datetime(user_doc.get("created_at")),
        "updated_at": _serialize_datetime(user_doc.get("updated_at")),
    }


def _validate_buildings_exist(
    repo: DataRepository,
    building_ids: list[str],
) -> list[str]:
    normalized = _dedupe_preserve_order(building_ids)
    if not normalized:
        return []
    try:
        available = {
            blob
            for blob in repo.list_blobs()
            if blob.lower().endswith((".xlsx", ".xls"))
        }
    except AzureDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Azure error",
        ) from exc
    missing = [item for item in normalized if item not in available]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown buildings: {', '.join(missing)}",
        )
    return normalized


def _resolve_company_scope(
    actor: CurrentUserContext,
    role: str,
    company_id: str | None,
) -> dict | None:
    if role == ROLE_VKALLPA_ADMIN:
        if actor.role != ROLE_VKALLPA_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden role",
            )
        return None

    target_company_id = company_id
    if actor.role == ROLE_COMPANY_ADMIN:
        target_company_id = actor.company_id
        if company_id and company_id != actor.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden company",
            )

    if not target_company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="company_id is required",
        )

    company_doc = _get_company_or_404(target_company_id)
    if (
        actor.role == ROLE_COMPANY_ADMIN
        and serialize_mongo_id(company_doc["_id"]) != actor.company_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden company",
        )
    return company_doc


def _resolve_user_permissions(
    role: str,
    requested_permissions: list[str] | None,
) -> list[str]:
    if role == ROLE_VKALLPA_ADMIN:
        return VKALLPA_ADMIN_MODULE_KEYS
    if role == ROLE_COMPANY_ADMIN:
        return COMPANY_ADMIN_MODULE_KEYS
    requested = _dedupe_preserve_order(
        requested_permissions or DEFAULT_COMPANY_USER_MODULE_KEYS
    )
    return [item for item in requested if item in BUSINESS_MODULE_KEYS]


def _resolve_user_buildings(
    role: str,
    requested_buildings: list[str] | None,
    company_doc: dict | None,
    repo: DataRepository,
) -> list[str]:
    if role == ROLE_VKALLPA_ADMIN:
        return _validate_buildings_exist(repo, requested_buildings or [])

    company_allowed = _validate_buildings_exist(
        repo,
        _dedupe_preserve_order(
            (company_doc or {}).get("allowed_building_ids", [])
        ),
    )
    if role == ROLE_COMPANY_ADMIN:
        return company_allowed

    requested = (
        requested_buildings
        if requested_buildings is not None
        else company_allowed
    )
    requested = _validate_buildings_exist(repo, requested)
    company_allowed_set = set(company_allowed)
    invalid = [item for item in requested if item not in company_allowed_set]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User buildings must be a subset of company buildings",
        )
    return requested


def _record_audit_log(
    actor: CurrentUserContext,
    tenant_id: str,
    action: str,
    target_id: str,
    details: dict,
) -> None:
    audit_logs = get_audit_logs_collection()
    audit_logs.insert_one(
        {
            "tenant_id": tenant_id,
            "action": action,
            "target_id": target_id,
            "actor_user_id": _parse_object_id(actor.user_id, "actor_id"),
            "details": details,
            "created_at": _utcnow(),
        }
    )


def _build_initial_admin_credentials(
    payload,
    tenant_id: str,
    company_name: str,
) -> dict:
    generated_password = payload.admin_password is None
    password = payload.admin_password or token_urlsafe(12)
    username = (payload.admin_username or f"admin@{tenant_id}").strip()
    full_name = (payload.admin_full_name or f"{company_name} Admin").strip()

    if not username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Initial admin username is required",
        )
    if not full_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Initial admin full name is required",
        )

    return {
        "username": username,
        "full_name": full_name,
        "password": password,
        "temporary_password": password if generated_password else None,
    }


def _create_initial_company_admin(
    actor: CurrentUserContext,
    company_doc: dict,
    payload,
    repo: DataRepository,
) -> dict:
    tenant_id = company_doc["tenant_id"]
    credentials = _build_initial_admin_credentials(
        payload,
        tenant_id,
        company_doc["name"],
    )
    now = _utcnow()
    admin_doc = {
        "username": credentials["username"],
        "full_name": credentials["full_name"],
        "password_hash": hash_password(credentials["password"]),
        "role": ROLE_COMPANY_ADMIN,
        "status": USER_STATUS_ACTIVE,
        "company_id": company_doc["_id"],
        "module_permissions": COMPANY_ADMIN_MODULE_KEYS,
        "allowed_building_ids": _resolve_user_buildings(
            ROLE_COMPANY_ADMIN,
            None,
            company_doc,
            repo,
        ),
        "created_by_user_id": _parse_object_id(actor.user_id, "actor_id"),
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }

    users = get_users_collection()
    try:
        result = users.insert_one(admin_doc)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Initial admin username already exists",
        ) from exc

    return {
        "id": serialize_mongo_id(result.inserted_id),
        "username": credentials["username"],
        "full_name": credentials["full_name"],
        "temporary_password": credentials["temporary_password"],
    }


def _build_update_changes(company: dict, update_fields: dict) -> dict:
    tracked_fields = {
        "tenant_id",
        "name",
        "slug",
        "status",
        "allowed_building_ids",
    }
    changes = {}
    for field in tracked_fields:
        if field in update_fields and company.get(field) != update_fields[field]:
            changes[field] = {
                "old": company.get(field),
                "new": update_fields[field],
            }
    return changes


def list_companies(actor: CurrentUserContext) -> list[dict]:
    if actor.role != ROLE_VKALLPA_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    companies = get_companies_collection()
    users = get_users_collection()
    items = []
    for company in companies.find().sort("name", 1):
        user_count = users.count_documents(
            {"company_id": company["_id"], "deleted_at": None}
        )
        items.append(_serialize_company(company, user_count=user_count))
    return items


def create_company(actor: CurrentUserContext, payload, repo: DataRepository) -> dict:
    if actor.role != ROLE_VKALLPA_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    companies = get_companies_collection()
    now = _utcnow()
    name = payload.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name is required",
        )

    tenant_id = _normalize_tenant_id(payload.tenant_id or payload.slug or name)
    slug = _normalize_slug(payload.slug or tenant_id)
    if not slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid company slug",
        )
    if companies.find_one({"tenant_id": tenant_id}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tenant ID already exists",
        )

    doc = {
        "tenant_id": tenant_id,
        "name": name,
        "slug": slug,
        "status": payload.status,
        "allowed_building_ids": _validate_buildings_exist(
            repo,
            payload.allowed_building_ids,
        ),
        "created_by_user_id": _parse_object_id(actor.user_id, "actor_id"),
        "created_at": now,
        "updated_at": now,
    }
    try:
        result = companies.insert_one(doc)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Company slug already exists",
        ) from exc
    company = companies.find_one({"_id": result.inserted_id}) or {
        **doc,
        "_id": result.inserted_id,
    }

    try:
        initial_admin = _create_initial_company_admin(actor, company, payload, repo)
    except HTTPException:
        companies.delete_one({"_id": result.inserted_id})
        raise

    company_id = serialize_mongo_id(company["_id"]) or ""
    _record_audit_log(
        actor,
        tenant_id,
        "tenant.created",
        company_id,
        {"name": name, "status": payload.status},
    )
    _record_audit_log(
        actor,
        tenant_id,
        "tenant.admin_created",
        initial_admin["id"],
        {"username": initial_admin["username"]},
    )
    return _serialize_company(company, user_count=1, initial_admin=initial_admin)


def update_company(
    actor: CurrentUserContext,
    company_id: str,
    payload,
    repo: DataRepository,
) -> dict:
    if actor.role != ROLE_VKALLPA_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    companies = get_companies_collection()
    users = get_users_collection()
    company = _get_company_or_404(company_id)

    update_fields: dict = {"updated_at": _utcnow()}
    if payload.tenant_id is not None:
        update_fields["tenant_id"] = _normalize_tenant_id(payload.tenant_id)
    if payload.name is not None:
        update_fields["name"] = payload.name.strip()
    if payload.slug is not None:
        slug = _normalize_slug(payload.slug)
        if not slug:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid company slug",
            )
        update_fields["slug"] = slug
    if payload.status is not None:
        update_fields["status"] = payload.status
    if payload.allowed_building_ids is not None:
        allowed_building_ids = _validate_buildings_exist(
            repo,
            payload.allowed_building_ids,
        )
        update_fields["allowed_building_ids"] = allowed_building_ids
    changes = _build_update_changes(company, update_fields)
    try:
        companies.update_one({"_id": company["_id"]}, {"$set": update_fields})
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tenant ID or company slug already exists",
        ) from exc

    if "allowed_building_ids" in update_fields:
        company_buildings = set(update_fields["allowed_building_ids"])
        for user_doc in users.find({"company_id": company["_id"], "deleted_at": None}):
            user_allowed = _dedupe_preserve_order(
                user_doc.get("allowed_building_ids", [])
            )
            if not user_allowed:
                continue
            clipped = [item for item in user_allowed if item in company_buildings]
            users.update_one(
                {"_id": user_doc["_id"]},
                {"$set": {"allowed_building_ids": clipped, "updated_at": _utcnow()}},
            )

    updated = companies.find_one({"_id": company["_id"]})
    user_count = users.count_documents(
        {"company_id": company["_id"], "deleted_at": None}
    )
    if changes and updated:
        tenant_id = (
            updated.get("tenant_id") or company.get("tenant_id") or company["slug"]
        )
        _record_audit_log(
            actor,
            tenant_id,
            "tenant.updated",
            serialize_mongo_id(company["_id"]) or "",
            {"changes": changes},
        )
    return _serialize_company(updated or company, user_count=user_count)


def list_users(actor: CurrentUserContext) -> list[dict]:
    if not actor.can_manage_users:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    users = get_users_collection()
    companies = get_companies_collection()

    query = {"deleted_at": None}
    if actor.role == ROLE_COMPANY_ADMIN:
        query["company_id"] = _parse_object_id(actor.company_id or "", "company_id")

    user_docs = list(users.find(query).sort("created_at", -1))
    company_ids = [
        doc.get("company_id") for doc in user_docs if doc.get("company_id")
    ]
    company_map = {
        company["_id"]: company
        for company in companies.find({"_id": {"$in": company_ids}})
    }

    return [
        _serialize_user(doc, company_map.get(doc.get("company_id")))
        for doc in user_docs
    ]


def create_user(actor: CurrentUserContext, payload, repo: DataRepository) -> dict:
    if not actor.can_manage_users:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if actor.role == ROLE_COMPANY_ADMIN and payload.role == ROLE_VKALLPA_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden role",
        )

    company_doc = _resolve_company_scope(actor, payload.role, payload.company_id)
    role = payload.role
    users = get_users_collection()
    now = _utcnow()

    doc = {
        "username": payload.username.strip(),
        "full_name": payload.full_name.strip(),
        "password_hash": hash_password(payload.password),
        "role": role,
        "status": payload.status,
        "company_id": company_doc["_id"] if company_doc else None,
        "module_permissions": _resolve_user_permissions(
            role,
            payload.module_permissions,
        ),
        "allowed_building_ids": _resolve_user_buildings(
            role,
            payload.allowed_building_ids,
            company_doc,
            repo,
        ),
        "created_by_user_id": _parse_object_id(actor.user_id, "actor_id"),
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }
    try:
        result = users.insert_one(doc)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        ) from exc

    created = users.find_one({"_id": result.inserted_id}) or doc
    return _serialize_user(created, company_doc)


def update_user(
    actor: CurrentUserContext,
    user_id: str,
    payload,
    repo: DataRepository,
) -> dict:
    if not actor.can_manage_users:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    users = get_users_collection()
    target = _get_user_or_404(user_id)
    target_company = _resolve_company(serialize_mongo_id(target.get("company_id")))

    if actor.role == ROLE_COMPANY_ADMIN:
        if serialize_mongo_id(target.get("company_id")) != actor.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden company",
            )
        if target["role"] == ROLE_VKALLPA_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden user",
            )

    next_role = payload.role or target["role"]
    if actor.role == ROLE_COMPANY_ADMIN and next_role == ROLE_VKALLPA_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden role",
        )

    company_id = (
        serialize_mongo_id(target.get("company_id"))
        if payload.company_id is None
        else payload.company_id
    )
    company_doc = _resolve_company_scope(actor, next_role, company_id)

    update_fields: dict = {"updated_at": _utcnow()}
    if payload.username is not None:
        update_fields["username"] = payload.username.strip()
    if payload.full_name is not None:
        update_fields["full_name"] = payload.full_name.strip()
    if payload.password:
        update_fields["password_hash"] = hash_password(payload.password)
    if payload.role is not None:
        update_fields["role"] = next_role
    if payload.status is not None:
        update_fields["status"] = payload.status
    update_fields["company_id"] = company_doc["_id"] if company_doc else None

    raw_permissions = (
        payload.module_permissions
        if payload.module_permissions is not None
        else target.get("module_permissions", [])
    )
    update_fields["module_permissions"] = _resolve_user_permissions(
        next_role,
        raw_permissions,
    )

    raw_buildings = (
        payload.allowed_building_ids
        if payload.allowed_building_ids is not None
        else target.get("allowed_building_ids", [])
    )
    update_fields["allowed_building_ids"] = _resolve_user_buildings(
        next_role,
        raw_buildings,
        company_doc,
        repo,
    )

    try:
        users.update_one({"_id": target["_id"]}, {"$set": update_fields})
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        ) from exc

    updated = users.find_one({"_id": target["_id"]}) or target
    return _serialize_user(updated, company_doc)


def delete_user(actor: CurrentUserContext, user_id: str) -> None:
    if not actor.can_manage_users:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if actor.user_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete current user",
        )

    users = get_users_collection()
    target = _get_user_or_404(user_id)
    if actor.role == ROLE_COMPANY_ADMIN:
        if serialize_mongo_id(target.get("company_id")) != actor.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden company",
            )
        if target["role"] == ROLE_VKALLPA_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden user",
            )

    users.update_one(
        {"_id": target["_id"]},
        {
            "$set": {
                "status": "inactive",
                "deleted_at": _utcnow(),
                "updated_at": _utcnow(),
            }
        },
    )
