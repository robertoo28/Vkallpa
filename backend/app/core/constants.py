from __future__ import annotations

ROLE_VKALLPA_ADMIN = "vkallpa_admin"
ROLE_COMPANY_ADMIN = "company_admin"
ROLE_COMPANY_USER = "company_user"

USER_STATUS_ACTIVE = "active"
USER_STATUS_INACTIVE = "inactive"

COMPANY_STATUS_ACTIVE = "active"
COMPANY_STATUS_INACTIVE = "inactive"
TENANT_SETTINGS_MODULE_KEY = "tenant-settings"

BUSINESS_MODULES = [
    {"key": "accueil", "label": "Accueil"},
    {"key": "parc-immobilier", "label": "Parc immobilier"},
    {"key": "monitoring", "label": "Monitoring"},
    {"key": "profils", "label": "Profils"},
    {"key": "puissance-max", "label": "Puissance Max"},
    {"key": "comparaison-puissance", "label": "Comparaison Puissance"},
    {"key": "meteo", "label": "Meteo"},
    {"key": "carbone", "label": "Carbone"},
    {"key": "comparaison-periode", "label": "Comparaison Periode"},
    {"key": "comparatif-batiments", "label": "Comparatif Batiments"},
    {"key": "autoconsommation", "label": "Autoconsommation"},
    {"key": "changepoints", "label": "Changepoints"},
    {"key": "anomalies", "label": "Anomalies"},
    {"key": "prediction", "label": "Prediction"},
    {"key": "nilm", "label": "NILM"},
]

ADMIN_MODULES = [
    {"key": "admin-users", "label": "Utilisateurs"},
    {"key": "admin-companies", "label": "Entreprises"},
    {"key": TENANT_SETTINGS_MODULE_KEY, "label": "Configuration tenant"},
]

ALL_MODULES = [*BUSINESS_MODULES, *ADMIN_MODULES]
BUSINESS_MODULE_KEYS = {item["key"] for item in BUSINESS_MODULES}
ADMIN_MODULE_KEYS = {item["key"] for item in ADMIN_MODULES}
ALL_MODULE_KEYS = {item["key"] for item in ALL_MODULES}

VKALLPA_ADMIN_MODULE_KEYS = sorted(ALL_MODULE_KEYS)
COMPANY_ADMIN_MODULE_KEYS = sorted(
    BUSINESS_MODULE_KEYS | {"admin-users", TENANT_SETTINGS_MODULE_KEY}
)
DEFAULT_COMPANY_USER_MODULE_KEYS = ["accueil", "monitoring"]

USER_ROLE_VALUES = {ROLE_VKALLPA_ADMIN, ROLE_COMPANY_ADMIN, ROLE_COMPANY_USER}
USER_STATUS_VALUES = {USER_STATUS_ACTIVE, USER_STATUS_INACTIVE}
COMPANY_STATUS_VALUES = {COMPANY_STATUS_ACTIVE, COMPANY_STATUS_INACTIVE}
