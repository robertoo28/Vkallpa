import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .admin.routes import router as admin_router
from .admin.routes import tenants_router
from .admin.routes import users_router
from .auth.dependencies import get_current_user
from .auth.routes import router as auth_router
from .core.mongo import close_database, initialize_database
from .core.settings import settings
from .data_sources.routes import router as data_sources_router
from .routers.accueil import router as accueil_router
from .routers.buildings import router as buildings_router
from .routers.dashboard_multi import router as dashboard_multi_router
from .routers.health import router as health_router
from .routers.ia import router as ia_router
from .routers.monitoring import router as monitoring_router
from .routers.placeholders import router as placeholders_router
from .routers.profils import router as profils_router
from .routers.puissance import router as puissance_router
from .routers.traitement import router as traitement_router
from .services.data_repository import AzureDataError, BuildingAccessError


def _configure_logging() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logs_dir = Path(__file__).resolve().parents[1] / "logs"
    logs_dir.mkdir(exist_ok=True)
    log_file = logs_dir / "api.log"

    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding="utf-8"),
    ]

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=handlers,
    )
    logging.getLogger("azure").setLevel(logging.WARNING)


_configure_logging()

app = FastAPI(title="V-Kallpa API")


@app.on_event("startup")
def startup_event() -> None:
    initialize_database()


@app.on_event("shutdown")
def shutdown_event() -> None:
    close_database()


@app.exception_handler(BuildingAccessError)
def building_access_exception_handler(
    _: Request,
    exc: BuildingAccessError,
) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc) or "Forbidden"})


@app.exception_handler(AzureDataError)
def azure_exception_handler(_: Request, __: AzureDataError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": "Azure error"})


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

public_router = APIRouter(prefix="/api/v1")
public_router.include_router(auth_router, prefix="/auth", tags=["auth"])
public_router.include_router(health_router, tags=["health"])

protected_router = APIRouter(prefix="/api/v1", dependencies=[Depends(get_current_user)])
protected_router.include_router(buildings_router, tags=["buildings"])
protected_router.include_router(accueil_router, tags=["accueil"])
protected_router.include_router(dashboard_multi_router, tags=["dashboard-multi"])
protected_router.include_router(monitoring_router, tags=["monitoring"])
protected_router.include_router(profils_router, tags=["profils"])
protected_router.include_router(puissance_router, tags=["puissance"])
protected_router.include_router(traitement_router, tags=["traitement"])
protected_router.include_router(ia_router, tags=["ia"])
protected_router.include_router(admin_router)
protected_router.include_router(tenants_router)
protected_router.include_router(users_router)
protected_router.include_router(data_sources_router)
protected_router.include_router(placeholders_router, tags=["placeholders"])

app.include_router(public_router)
app.include_router(protected_router)
