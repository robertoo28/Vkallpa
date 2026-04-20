import mongomock
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.auth.dependencies import get_data_repository
from backend.app.core.mongo import (
    get_audit_logs_collection,
    reset_database_state,
    set_test_database,
)
from backend.app.core.settings import settings
from backend.app.main import app


class FakeRepo:
    def __init__(self) -> None:
        self._buildings = ["alpha.xlsx", "beta.xlsx", "gamma.xlsx"]
        self._df = pd.DataFrame(
            {
                "Date": pd.date_range("2024-01-01", periods=48, freq="h"),
                "Energie_periode_kWh": [1.0] * 48,
                "Puissance_moyenne_kW": [2.0] * 48,
            }
        )

    def list_blobs(self):
        return self._buildings

    def get_date_range(self, blob_name: str):
        if blob_name not in self._buildings:
            raise RuntimeError("Missing blob")
        return ("2024-01-01", "2024-01-02")

    def load_excel(self, blob_name: str, sheet_name: str):
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


def test_bootstrap_admin_can_login_and_fetch_profile(client: TestClient):
    login_payload = login(client, "admin", "admin")
    assert login_payload["user"]["role"] == "vkallpa_admin"
    assert "admin-companies" in login_payload["user"]["module_permissions"]

    me_response = client.get(
        "/api/v1/auth/me",
        headers=auth_headers(login_payload["access_token"]),
    )
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "admin"


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
        f"/api/v1/admin/users/{user_id}",
        headers=admin_headers,
    )
    assert delete_response.status_code == 204

    me_response = client.get("/api/v1/auth/me", headers=user_headers)
    assert me_response.status_code == 401
