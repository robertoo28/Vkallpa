from __future__ import annotations

from pathlib import Path
from typing import List

from dotenv import load_dotenv
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


_root_env = Path(__file__).resolve().parents[3] / ".env"
_backend_env = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(_root_env)
load_dotenv(_backend_env)


class Settings(BaseSettings):
    mongo_uri: str = Field(
        "mongodb://localhost:27017",
        validation_alias=AliasChoices("MONGO_URI", "mongo_uri"),
    )
    mongo_db_name: str = Field(
        "vkallpa",
        validation_alias=AliasChoices("MONGO_DB_NAME", "mongo_db_name"),
    )
    mongo_root_username: str = Field(
        "vkallpa",
        validation_alias=AliasChoices("MONGO_ROOT_USERNAME", "mongo_root_username"),
    )
    mongo_root_password: str = Field(
        "vkallpa_dev",
        validation_alias=AliasChoices("MONGO_ROOT_PASSWORD", "mongo_root_password"),
    )
    bootstrap_admin_username: str = Field(
        "admin",
        validation_alias=AliasChoices(
            "BOOTSTRAP_ADMIN_USERNAME",
            "AUTH_USERNAME",
            "bootstrap_admin_username",
        ),
    )
    bootstrap_admin_password_hash: str = Field(
        "plain:admin",
        validation_alias=AliasChoices(
            "BOOTSTRAP_ADMIN_PASSWORD_HASH",
            "AUTH_PASSWORD_HASH",
            "bootstrap_admin_password_hash",
        ),
    )
    jwt_secret: str = Field(
        "change_me",
        validation_alias=AliasChoices("JWT_SECRET", "jwt_secret"),
    )
    jwt_expire_minutes: int = Field(
        60,
        validation_alias=AliasChoices("JWT_EXPIRE_MINUTES", "jwt_expire_minutes"),
    )
    jwt_refresh_expire_minutes: int = Field(
        10080,
        validation_alias=AliasChoices(
            "JWT_REFRESH_EXPIRE_MINUTES",
            "jwt_refresh_expire_minutes",
        ),
    )
    jwt_algorithm: str = "HS256"
    cors_allow_origins: List[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()  # pyright: ignore[reportCallIssue]
