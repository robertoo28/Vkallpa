from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from .constants import (
    ROLE_VKALLPA_ADMIN,
    USER_STATUS_ACTIVE,
    VKALLPA_ADMIN_MODULE_KEYS,
)
from .security import ensure_password_hash
from .settings import settings


_client: MongoClient | None = None
_database: Database | None = None
_initialized = False


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_database() -> Database:
    global _client, _database
    if _database is None:
        _client = MongoClient(settings.mongo_uri)
        _database = _client[settings.mongo_db_name]
    return _database


def get_users_collection() -> Collection:
    return get_database()["users"]


def get_companies_collection() -> Collection:
    return get_database()["companies"]


def get_audit_logs_collection() -> Collection:
    return get_database()["audit_logs"]


def get_email_outbox_collection() -> Collection:
    return get_database()["email_outbox"]


def get_password_reset_tokens_collection() -> Collection:
    return get_database()["password_reset_tokens"]


def get_data_sources_collection() -> Collection:
    """Return the tenant data source configuration collection."""
    return get_database()["data_sources"]


def initialize_database() -> None:
    global _initialized
    if _initialized:
        return

    db = get_database()
    users = db["users"]
    companies = db["companies"]
    audit_logs = db["audit_logs"]
    email_outbox = db["email_outbox"]
    password_reset_tokens = db["password_reset_tokens"]
    data_sources = db["data_sources"]

    users.create_index(
        [("username", ASCENDING)],
        unique=True,
        name="users_username_unique",
    )
    users.create_index([("company_id", ASCENDING)], name="users_company_id_idx")
    companies.create_index(
        [("slug", ASCENDING)],
        unique=True,
        name="companies_slug_unique",
    )
    companies.create_index(
        [("tenant_id", ASCENDING)],
        unique=True,
        sparse=True,
        name="companies_tenant_id_unique",
    )
    audit_logs.create_index([("tenant_id", ASCENDING)], name="audit_logs_tenant_id_idx")
    audit_logs.create_index(
        [("actor_user_id", ASCENDING)],
        name="audit_logs_actor_user_id_idx",
    )
    audit_logs.create_index(
        [("created_at", ASCENDING)],
        name="audit_logs_created_at_idx",
    )
    email_outbox.create_index(
        [("recipient", ASCENDING)],
        name="email_outbox_recipient_idx",
    )
    email_outbox.create_index(
        [("created_at", ASCENDING)],
        name="email_outbox_created_at_idx",
    )
    password_reset_tokens.create_index(
        [("token_hash", ASCENDING)],
        unique=True,
        name="password_reset_token_hash_unique",
    )
    password_reset_tokens.create_index(
        [("user_id", ASCENDING)],
        name="password_reset_user_id_idx",
    )
    password_reset_tokens.create_index(
        [("expires_at", ASCENDING)],
        name="password_reset_expires_at_idx",
    )
    data_sources.create_index(
        [("tenant_id", ASCENDING)],
        unique=True,
        name="data_sources_tenant_id_unique",
    )

    if users.count_documents({"deleted_at": None}) == 0:
        now = _utcnow()
        users.insert_one(
            {
                "username": settings.bootstrap_admin_username,
                "full_name": "Bootstrap Admin",
                "password_hash": ensure_password_hash(
                    settings.bootstrap_admin_password_hash
                ),
                "role": ROLE_VKALLPA_ADMIN,
                "status": USER_STATUS_ACTIVE,
                "company_id": None,
                "module_permissions": VKALLPA_ADMIN_MODULE_KEYS,
                "allowed_building_ids": [],
                "created_by_user_id": None,
                "created_at": now,
                "updated_at": now,
                "deleted_at": None,
            }
        )

    _initialized = True


def close_database() -> None:
    global _client, _database, _initialized
    if _client is not None:
        _client.close()
    _client = None
    _database = None
    _initialized = False


def set_test_database(database: Database) -> None:
    global _client, _database, _initialized
    _client = None
    _database = database
    _initialized = False


def reset_database_state() -> None:
    close_database()


def serialize_mongo_id(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
