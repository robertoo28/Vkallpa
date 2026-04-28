from datetime import datetime, timedelta, timezone
import io

import mongomock
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from jose import jwt

from backend.app.auth.dependencies import get_data_repository
from backend.app.core.mongo import (
    get_audit_logs_collection,
    get_email_outbox_collection,
    reset_database_state,
    set_test_database,
)
from backend.app.core.settings import settings
from backend.app.main import app


class FakeRepo:
    def __init__(self) -> None:
        self._buildings = ["alpha.xlsx", "beta.xlsx", "gamma.xlsx"]
        self._blobs = [*self._buildings, "meter-data.csv", "notes.txt"]
        self._df = pd.DataFrame(
            {
                "Date": pd.date_range("2024-01-01", periods=48, freq="h"),
                "Energie_periode_kWh": [1.0] * 48,
                "Puissance_moyenne_kW": [2.0] * 48,
                "Batiment": ["alpha"] * 48,
            }
        )

    def list_blobs(self) -> list[str]:
        return self._blobs

    def download_blob_bytes(self, blob_name: str) -> bytes:
        if blob_name == "meter-data.csv":
            return self._df.to_csv(index=False).encode("utf-8")
        if blob_name in self._buildings:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                self._df.to_excel(
                    writer,
                    index=False,
                    sheet_name="Donnees_Detaillees",
                )
            return buffer.getvalue()
        raise RuntimeError("Missing blob")

    def get_date_range(self, blob_name: str) -> tuple[str, str]:
        if blob_name not in self._buildings:
            raise RuntimeError("Missing blob")
        return ("2024-01-01", "2024-01-02")

    def load_excel(self, blob_name: str, sheet_name: str) -> pd.DataFrame:
        if blob_name not in self._buildings:
            raise RuntimeError("Missing blob")
        return self._df.copy()


@pytest.fixture
def client():
    database = mongomock.MongoClient()["vkallpa_test"]
    old_username = settings.bootstrap_admin_username
    old_password_hash = settings.bootstrap_admin_password_hash
    old_jwt_secret = settings.jwt_secret

    settings.bootstrap_admin_username = "admin"
    settings.bootstrap_admin_password_hash = "plain:admin"
    settings.jwt_secret = "test-secret"

    reset_database_state()
    set_test_database(database)
    app.dependency_overrides[get_data_repository] = lambda: FakeRepo()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    reset_database_state()
    settings.bootstrap_admin_username = old_username
    settings.bootstrap_admin_password_hash = old_password_hash
    settings.jwt_secret = old_jwt_secret


def login(client: TestClient, username: str, password: str) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def build_test_token(
    user_id: str,
    tenant_id: str | None,
    role: str,
    expires_delta: timedelta,
    token_type: str = "access",
) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": user_id,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "role": role,
            "type": token_type,
            "iat": int(now.timestamp()),
            "exp": now + expires_delta,
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def test_bootstrap_admin_can_login_and_fetch_profile(client: TestClient):
    login_payload = login(client, "admin", "admin")
    assert login_payload["user"]["role"] == "vkallpa_admin"
    assert "admin-companies" in login_payload["user"]["module_permissions"]
    assert login_payload["refresh_token"]

    me_response = client.get(
        "/api/v1/auth/me",
        headers=auth_headers(login_payload["access_token"]),
    )
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "admin"


def test_login_accepts_email_and_returns_jwt_claims(client: TestClient):
    admin = login(client, "admin", "admin")
    admin_headers = auth_headers(admin["access_token"])

    tenant = client.post(
        "/api/v1/tenants",
        headers=admin_headers,
        json={
            "tenant_id": "jwt-power",
            "name": "JWT Power",
            "allowed_building_ids": ["alpha.xlsx"],
            "admin_username": "jwt-admin@example.com",
            "admin_full_name": "JWT Admin",
            "admin_password": "secret1",
        },
    )
    assert tenant.status_code == 201, tenant.text

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "jwt-admin@example.com", "password": "secret1"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    claims = jwt.decode(
        payload["access_token"],
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )
    assert claims["type"] == "access"
    assert claims["user_id"] == payload["user"]["id"]
    assert claims["tenant_id"] == "jwt-power"
    assert claims["role"] == "company_admin"
    assert payload["refresh_token"]
    assert payload["refresh_expires_in"] > payload["expires_in"]

    refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": payload["refresh_token"]},
    )
    assert refresh.status_code == 200, refresh.text
    assert refresh.json()["user"]["username"] == "jwt-admin@example.com"


def test_login_rejects_incorrect_credentials(client: TestClient):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_expired_token_is_rejected(client: TestClient):
    admin = login(client, "admin", "admin")
    expired_token = build_test_token(
        user_id=admin["user"]["id"],
        tenant_id=None,
        role="vkallpa_admin",
        expires_delta=timedelta(minutes=-1),
    )

    response = client.get(
        "/api/v1/auth/me",
        headers=auth_headers(expired_token),
    )

    assert response.status_code == 401


def test_token_with_incorrect_tenant_is_rejected(client: TestClient):
    admin = login(client, "admin", "admin")
    admin_headers = auth_headers(admin["access_token"])

    tenant = client.post(
        "/api/v1/tenants",
        headers=admin_headers,
        json={
            "tenant_id": "tenant-token",
            "name": "Tenant Token",
            "allowed_building_ids": ["alpha.xlsx"],
            "admin_username": "tenant-token-admin",
            "admin_full_name": "Tenant Token Admin",
            "admin_password": "secret1",
        },
    )
    assert tenant.status_code == 201, tenant.text

    tenant_admin = login(client, "tenant-token-admin", "secret1")
    wrong_tenant_token = build_test_token(
        user_id=tenant_admin["user"]["id"],
        tenant_id="other-tenant",
        role="company_admin",
        expires_delta=timedelta(minutes=5),
    )

    response = client.get(
        "/api/v1/auth/me",
        headers=auth_headers(wrong_tenant_token),
    )

    assert response.status_code == 401


def test_create_tenant_generates_initial_admin_and_audit_log(client: TestClient):
    admin = login(client, "admin", "admin")
    admin_headers = auth_headers(admin["access_token"])

    response = client.post(
        "/api/v1/tenants",
        headers=admin_headers,
        json={
            "tenant_id": "green-power",
            "name": "Green Power",
            "allowed_building_ids": ["alpha.xlsx"],
            "admin_username": "green-admin",
            "admin_full_name": "Green Admin",
            "admin_password": "secret1",
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["tenant_id"] == "green-power"
    assert payload["initial_admin"]["username"] == "green-admin"
    assert payload["user_count"] == 1

    tenant_admin = login(client, "green-admin", "secret1")
    assert tenant_admin["user"]["role"] == "company_admin"
    assert tenant_admin["user"]["company"]["id"] == payload["id"]

    audit_actions = {
        item["action"]
        for item in get_audit_logs_collection().find({"tenant_id": "green-power"})
    }
    assert {"tenant.created", "tenant.admin_created"} <= audit_actions


def test_create_tenant_rejects_duplicate_tenant_id(client: TestClient):
    admin = login(client, "admin", "admin")
    admin_headers = auth_headers(admin["access_token"])

    first = client.post(
        "/api/v1/tenants",
        headers=admin_headers,
        json={
            "tenant_id": "duplicate-tenant",
            "name": "Duplicate Tenant",
            "allowed_building_ids": ["alpha.xlsx"],
            "admin_username": "duplicate-admin",
            "admin_full_name": "Duplicate Admin",
            "admin_password": "secret1",
        },
    )
    assert first.status_code == 201, first.text

    second = client.post(
        "/api/v1/tenants",
        headers=admin_headers,
        json={
            "tenant_id": "duplicate-tenant",
            "name": "Duplicate Tenant 2",
            "allowed_building_ids": ["beta.xlsx"],
            "admin_username": "duplicate-admin-2",
            "admin_full_name": "Duplicate Admin 2",
            "admin_password": "secret2",
        },
    )
    assert second.status_code == 409
    assert second.json()["detail"] == "Tenant ID already exists"


def test_update_tenant_records_audit_log(client: TestClient):
    admin = login(client, "admin", "admin")
    admin_headers = auth_headers(admin["access_token"])

    created = client.post(
        "/api/v1/tenants",
        headers=admin_headers,
        json={
            "tenant_id": "audit-power",
            "name": "Audit Power",
            "allowed_building_ids": ["alpha.xlsx"],
            "admin_username": "audit-admin",
            "admin_full_name": "Audit Admin",
            "admin_password": "secret1",
        },
    )
    assert created.status_code == 201, created.text

    updated = client.put(
        "/api/v1/tenants/audit-power",
        headers=admin_headers,
        json={
            "tenant_id": "audit-power",
            "name": "Audit Power Updated",
            "status": "inactive",
            "allowed_building_ids": ["beta.xlsx"],
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Audit Power Updated"
    assert updated.json()["status"] == "inactive"

    audit_log = get_audit_logs_collection().find_one(
        {"tenant_id": "audit-power", "action": "tenant.updated"}
    )
    assert audit_log is not None
    assert audit_log["details"]["changes"]["status"]["new"] == "inactive"


def test_update_tenant_config_validates_categories_and_records_audit_log(
    client: TestClient,
):
    admin = login(client, "admin", "admin")
    admin_headers = auth_headers(admin["access_token"])

    created = client.post(
        "/api/v1/tenants",
        headers=admin_headers,
        json={
            "tenant_id": "config-power",
            "name": "Config Power",
            "allowed_building_ids": ["alpha.xlsx"],
            "admin_username": "config-admin",
            "admin_full_name": "Config Admin",
            "admin_password": "secret1",
        },
    )
    assert created.status_code == 201, created.text

    updated = client.patch(
        "/api/v1/tenants/config-power/config",
        headers=admin_headers,
        json={
            "general": {"timezone": "America/Lima", "language": "es"},
            "energy": {"tariff_per_kwh": 0.18},
            "reports": {"default_period": "weekly"},
        },
    )
    assert updated.status_code == 200, updated.text
    payload = updated.json()
    assert payload["general"]["timezone"] == "America/Lima"
    assert payload["energy"]["tariff_per_kwh"] == 0.18
    assert payload["reports"]["default_period"] == "weekly"

    audit_log = get_audit_logs_collection().find_one(
        {"tenant_id": "config-power", "action": "tenant.config_updated"}
    )
    assert audit_log is not None
    assert audit_log["details"]["changes"]["energy"]["tariff_per_kwh"] == {
        "old": 0.12,
        "new": 0.18,
    }

    invalid_category = client.patch(
        "/api/v1/tenants/config-power/config",
        headers=admin_headers,
        json={"billing": {"enabled": True}},
    )
    assert invalid_category.status_code == 422

    invalid_value = client.patch(
        "/api/v1/tenants/config-power/config",
        headers=admin_headers,
        json={"energy": {"tariff_per_kwh": -1}},
    )
    assert invalid_value.status_code == 422


def test_company_admin_updates_only_own_tenant_config(client: TestClient):
    admin = login(client, "admin", "admin")
    admin_headers = auth_headers(admin["access_token"])

    own_tenant = client.post(
        "/api/v1/tenants",
        headers=admin_headers,
        json={
            "tenant_id": "own-tenant",
            "name": "Own Tenant",
            "allowed_building_ids": ["alpha.xlsx"],
            "admin_username": "own-admin",
            "admin_full_name": "Own Admin",
            "admin_password": "secret1",
        },
    )
    assert own_tenant.status_code == 201, own_tenant.text

    other_tenant = client.post(
        "/api/v1/tenants",
        headers=admin_headers,
        json={
            "tenant_id": "other-tenant",
            "name": "Other Tenant",
            "allowed_building_ids": ["beta.xlsx"],
            "admin_username": "other-admin",
            "admin_full_name": "Other Admin",
            "admin_password": "secret2",
        },
    )
    assert other_tenant.status_code == 201, other_tenant.text

    company_admin = login(client, "own-admin", "secret1")
    company_admin_headers = auth_headers(company_admin["access_token"])

    own_update = client.patch(
        "/api/v1/tenants/own-tenant/config",
        headers=company_admin_headers,
        json={"alerts": {"enabled": False}},
    )
    assert own_update.status_code == 200, own_update.text
    assert own_update.json()["alerts"]["enabled"] is False

    forbidden = client.patch(
        "/api/v1/tenants/other-tenant/config",
        headers=company_admin_headers,
        json={"alerts": {"enabled": False}},
    )
    assert forbidden.status_code == 403


def build_data_source_payload(
    tenant_id: str | None,
    container_name: str = "energy-data",
) -> dict:
    return {
        "tenant_id": tenant_id,
        "source_type": "azure_blob",
        "name": "Azure Blob Storage",
        "container_name": container_name,
        "blob_prefix": "",
        "default_sheet_name": "Donnees_Detaillees",
        "field_mapping": {
            "timestamp": "Date",
            "energy_kwh": "Energie_periode_kWh",
            "power_kw": "Puissance_moyenne_kW",
            "site": "Batiment",
        },
    }


def test_data_source_config_is_associated_with_tenant(
    client: TestClient,
) -> None:
    admin = login(client, "admin", "admin")
    admin_headers = auth_headers(admin["access_token"])

    tenant = client.post(
        "/api/v1/tenants",
        headers=admin_headers,
        json={
            "tenant_id": "source-tenant",
            "name": "Source Tenant",
            "allowed_building_ids": ["alpha.xlsx"],
            "admin_username": "source-admin@example.com",
            "admin_full_name": "Source Admin",
            "admin_password": "secret1",
        },
    )
    assert tenant.status_code == 201, tenant.text

    response = client.put(
        "/api/v1/data-sources",
        headers=admin_headers,
        json=build_data_source_payload("source-tenant"),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["tenant_id"] == "source-tenant"
    assert payload["container_name"] == "energy-data"
    assert payload["field_mapping"]["timestamp"] == "Date"

    fetched = client.get(
        "/api/v1/data-sources?tenant_id=source-tenant",
        headers=admin_headers,
    )
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["id"] == payload["id"]


def test_company_admin_manages_only_own_data_source(client: TestClient) -> None:
    admin = login(client, "admin", "admin")
    admin_headers = auth_headers(admin["access_token"])

    own_tenant = client.post(
        "/api/v1/tenants",
        headers=admin_headers,
        json={
            "tenant_id": "own-source",
            "name": "Own Source",
            "allowed_building_ids": ["alpha.xlsx"],
            "admin_username": "own-source-admin@example.com",
            "admin_full_name": "Own Source Admin",
            "admin_password": "secret1",
        },
    )
    assert own_tenant.status_code == 201, own_tenant.text

    other_tenant = client.post(
        "/api/v1/tenants",
        headers=admin_headers,
        json={
            "tenant_id": "other-source",
            "name": "Other Source",
            "allowed_building_ids": ["beta.xlsx"],
            "admin_username": "other-source-admin@example.com",
            "admin_full_name": "Other Source Admin",
            "admin_password": "secret2",
        },
    )
    assert other_tenant.status_code == 201, other_tenant.text

    company_admin = login(client, "own-source-admin@example.com", "secret1")
    company_admin_headers = auth_headers(company_admin["access_token"])

    own_update = client.put(
        "/api/v1/data-sources",
        headers=company_admin_headers,
        json=build_data_source_payload("own-source"),
    )
    assert own_update.status_code == 200, own_update.text
    assert own_update.json()["tenant_id"] == "own-source"

    forbidden = client.get(
        "/api/v1/data-sources?tenant_id=other-source",
        headers=company_admin_headers,
    )
    assert forbidden.status_code == 403


def test_data_source_files_and_preview_validation(client: TestClient) -> None:
    admin = login(client, "admin", "admin")
    admin_headers = auth_headers(admin["access_token"])

    tenant = client.post(
        "/api/v1/tenants",
        headers=admin_headers,
        json={
            "tenant_id": "preview-source",
            "name": "Preview Source",
            "allowed_building_ids": ["alpha.xlsx"],
            "admin_username": "preview-source-admin@example.com",
            "admin_full_name": "Preview Source Admin",
            "admin_password": "secret1",
        },
    )
    assert tenant.status_code == 201, tenant.text

    saved = client.put(
        "/api/v1/data-sources",
        headers=admin_headers,
        json=build_data_source_payload("preview-source"),
    )
    assert saved.status_code == 200, saved.text

    files = client.get(
        "/api/v1/data-sources/files?tenant_id=preview-source",
        headers=admin_headers,
    )
    assert files.status_code == 200, files.text
    assert {item["name"] for item in files.json()["items"]} == {
        "alpha.xlsx",
        "beta.xlsx",
        "gamma.xlsx",
        "meter-data.csv",
    }

    valid_preview = client.post(
        "/api/v1/data-sources/preview",
        headers=admin_headers,
        json={
            "tenant_id": "preview-source",
            "blob_name": "meter-data.csv",
        },
    )
    assert valid_preview.status_code == 200, valid_preview.text
    assert valid_preview.json()["is_valid"] is True
    assert valid_preview.json()["rows"][0]["Batiment"] == "alpha"

    invalid_preview = client.post(
        "/api/v1/data-sources/preview",
        headers=admin_headers,
        json={
            "tenant_id": "preview-source",
            "blob_name": "meter-data.csv",
            "field_mapping": {
                "timestamp": "Date",
                "energy_kwh": "Missing energy",
            },
        },
    )
    assert invalid_preview.status_code == 200, invalid_preview.text
    assert invalid_preview.json()["is_valid"] is False
    assert invalid_preview.json()["validation_errors"] == [
        {
            "field": "energy_kwh",
            "column": "Missing energy",
            "message": "Mapped column was not found in the file",
            "invalid_count": None,
        }
    ]


def test_vkallpa_admin_and_company_admin_manage_users_by_scope(client: TestClient):
    admin = login(client, "admin", "admin")
    admin_headers = auth_headers(admin["access_token"])

    company = client.post(
        "/api/v1/admin/companies",
        headers=admin_headers,
        json={
            "name": "Acme",
            "allowed_building_ids": ["alpha.xlsx", "beta.xlsx"],
        },
    )
    assert company.status_code == 201, company.text
    company_id = company.json()["id"]

    second_company = client.post(
        "/api/v1/admin/companies",
        headers=admin_headers,
        json={
            "name": "Other",
            "allowed_building_ids": ["gamma.xlsx"],
        },
    )
    assert second_company.status_code == 201, second_company.text

    company_admin = client.post(
        "/api/v1/admin/users",
        headers=admin_headers,
        json={
            "username": "acme-admin",
            "full_name": "Acme Admin",
            "password": "secret1",
            "role": "company_admin",
            "company_id": company_id,
        },
    )
    assert company_admin.status_code == 201, company_admin.text

    admin_login = login(client, "acme-admin", "secret1")
    company_admin_headers = auth_headers(admin_login["access_token"])

    user_response = client.post(
        "/api/v1/admin/users",
        headers=company_admin_headers,
        json={
            "username": "acme-user",
            "full_name": "Acme User",
            "password": "secret2",
            "role": "company_user",
            "module_permissions": ["monitoring"],
            "allowed_building_ids": ["alpha.xlsx"],
        },
    )
    assert user_response.status_code == 201, user_response.text
    assert user_response.json()["company"]["id"] == company_id

    forbidden = client.post(
        "/api/v1/admin/users",
        headers=company_admin_headers,
        json={
            "username": "forbidden",
            "full_name": "Forbidden User",
            "password": "secret3",
            "role": "company_user",
            "company_id": second_company.json()["id"],
            "module_permissions": ["monitoring"],
            "allowed_building_ids": ["gamma.xlsx"],
        },
    )
    assert forbidden.status_code == 403


def test_create_user_respects_quota_and_queues_invitation(client: TestClient):
    admin = login(client, "admin", "admin")
    admin_headers = auth_headers(admin["access_token"])

    company = client.post(
        "/api/v1/tenants",
        headers=admin_headers,
        json={
            "tenant_id": "quota-tenant",
            "name": "Quota Tenant",
            "user_quota": 2,
            "allowed_building_ids": ["alpha.xlsx"],
            "admin_username": "quota-admin@example.com",
            "admin_full_name": "Quota Admin",
            "admin_password": "secret1",
        },
    )
    assert company.status_code == 201, company.text

    company_admin = login(client, "quota-admin@example.com", "secret1")
    company_admin_headers = auth_headers(company_admin["access_token"])

    user_response = client.post(
        "/api/v1/users",
        headers=company_admin_headers,
        json={
            "username": "quota-user@example.com",
            "full_name": "Quota User",
            "role": "company_user",
            "module_permissions": ["accueil"],
            "allowed_building_ids": ["alpha.xlsx"],
        },
    )
    assert user_response.status_code == 201, user_response.text
    payload = user_response.json()
    assert payload["invitation_sent"] is True
    assert payload["temporary_password"]

    invitation = get_email_outbox_collection().find_one(
        {
            "recipient": "quota-user@example.com",
            "metadata.type": "user_invitation",
        }
    )
    assert invitation is not None
    assert invitation["metadata"]["temporary_password"] == payload["temporary_password"]

    over_quota = client.post(
        "/api/v1/users",
        headers=company_admin_headers,
        json={
            "username": "quota-user-2@example.com",
            "full_name": "Quota User 2",
            "role": "company_user",
            "module_permissions": ["accueil"],
            "allowed_building_ids": ["alpha.xlsx"],
        },
    )
    assert over_quota.status_code == 409
    assert over_quota.json()["detail"] == "User quota exceeded"


def test_company_user_is_limited_to_allowed_buildings(client: TestClient):
    admin = login(client, "admin", "admin")
    admin_headers = auth_headers(admin["access_token"])

    company = client.post(
        "/api/v1/admin/companies",
        headers=admin_headers,
        json={
            "name": "Scoped Co",
            "allowed_building_ids": ["alpha.xlsx", "beta.xlsx"],
        },
    )
    company_id = company.json()["id"]

    user = client.post(
        "/api/v1/admin/users",
        headers=admin_headers,
        json={
            "username": "viewer",
            "full_name": "Viewer",
            "password": "secret4",
            "role": "company_user",
            "company_id": company_id,
            "module_permissions": ["monitoring"],
            "allowed_building_ids": ["alpha.xlsx"],
        },
    )
    assert user.status_code == 201, user.text

    viewer_login = login(client, "viewer", "secret4")
    viewer_headers = auth_headers(viewer_login["access_token"])

    buildings = client.get("/api/v1/buildings", headers=viewer_headers)
    assert buildings.status_code == 200
    assert [item["id"] for item in buildings.json()["items"]] == ["alpha.xlsx"]

    allowed = client.get(
        "/api/v1/monitoring/graphs?building=alpha.xlsx",
        headers=viewer_headers,
    )
    assert allowed.status_code == 200

    forbidden = client.get(
        "/api/v1/monitoring/graphs?building=beta.xlsx",
        headers=viewer_headers,
    )
    assert forbidden.status_code == 403


def test_deleted_user_token_becomes_invalid(client: TestClient):
    admin = login(client, "admin", "admin")
    admin_headers = auth_headers(admin["access_token"])

    company = client.post(
        "/api/v1/admin/companies",
        headers=admin_headers,
        json={
            "name": "Delete Co",
            "allowed_building_ids": ["alpha.xlsx"],
        },
    )
    company_id = company.json()["id"]

    user = client.post(
        "/api/v1/admin/users",
        headers=admin_headers,
        json={
            "username": "to-delete",
            "full_name": "To Delete",
            "password": "secret5",
            "role": "company_user",
            "company_id": company_id,
            "module_permissions": ["accueil"],
            "allowed_building_ids": ["alpha.xlsx"],
        },
    )
    user_id = user.json()["id"]

    user_login = login(client, "to-delete", "secret5")
    user_headers = auth_headers(user_login["access_token"])

    delete_response = client.delete(
        f"/api/v1/users/{user_id}",
        headers=admin_headers,
    )
    assert delete_response.status_code == 204

    users = client.get("/api/v1/users", headers=admin_headers)
    assert users.status_code == 200
    inactive_user = next(
        item for item in users.json()["items"] if item["id"] == user_id
    )
    assert inactive_user["status"] == "inactive"

    me_response = client.get("/api/v1/auth/me", headers=user_headers)
    assert me_response.status_code == 401


def test_password_reset_flow_uses_one_time_token(client: TestClient):
    admin = login(client, "admin", "admin")
    admin_headers = auth_headers(admin["access_token"])

    tenant = client.post(
        "/api/v1/tenants",
        headers=admin_headers,
        json={
            "tenant_id": "reset-tenant",
            "name": "Reset Tenant",
            "allowed_building_ids": ["alpha.xlsx"],
            "admin_username": "reset-admin@example.com",
            "admin_full_name": "Reset Admin",
            "admin_password": "secret1",
        },
    )
    assert tenant.status_code == 201, tenant.text

    request = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "reset-admin@example.com"},
    )
    assert request.status_code == 200, request.text

    reset_email = get_email_outbox_collection().find_one(
        {
            "recipient": "reset-admin@example.com",
            "metadata.type": "password_reset",
        }
    )
    assert reset_email is not None
    reset_token = reset_email["metadata"]["token"]

    confirm = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": reset_token, "password": "new-secret"},
    )
    assert confirm.status_code == 200, confirm.text

    old_login = client.post(
        "/api/v1/auth/login",
        json={"email": "reset-admin@example.com", "password": "secret1"},
    )
    assert old_login.status_code == 401

    new_login = login(client, "reset-admin@example.com", "new-secret")
    assert new_login["user"]["username"] == "reset-admin@example.com"

    reused = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": reset_token, "password": "another-secret"},
    )
    assert reused.status_code == 400
