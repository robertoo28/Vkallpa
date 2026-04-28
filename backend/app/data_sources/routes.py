from fastapi import APIRouter, Depends

from ..auth.dependencies import (
    get_current_user,
    get_data_repository,
    require_module_access,
)
from ..auth.service import CurrentUserContext
from ..core.constants import DATA_SOURCES_MODULE_KEY
from ..services.data_repository import DataRepository
from .schemas import (
    DataSourceConfigRequest,
    DataSourceConfigResponse,
    DataSourceFilesResponse,
    DataSourcePreviewRequest,
    DataSourcePreviewResponse,
)
from .service import (
    get_data_source_config,
    list_data_source_files,
    preview_data_source_file,
    save_data_source_config,
)


router = APIRouter(
    prefix="/data-sources",
    tags=["data-sources"],
    dependencies=[Depends(require_module_access(DATA_SOURCES_MODULE_KEY))],
)


@router.get("", response_model=DataSourceConfigResponse)
def get_data_source(
    tenant_id: str | None = None,
    current_user: CurrentUserContext = Depends(get_current_user),
) -> DataSourceConfigResponse:
    """Return the source configuration associated with a tenant."""
    return DataSourceConfigResponse.model_validate(
        get_data_source_config(current_user, tenant_id)
    )


@router.put("", response_model=DataSourceConfigResponse)
def put_data_source(
    payload: DataSourceConfigRequest,
    current_user: CurrentUserContext = Depends(get_current_user),
) -> DataSourceConfigResponse:
    """Create or update the source configuration associated with a tenant."""
    return DataSourceConfigResponse.model_validate(
        save_data_source_config(current_user, payload)
    )


@router.get("/files", response_model=DataSourceFilesResponse)
def get_data_source_files(
    tenant_id: str | None = None,
    current_user: CurrentUserContext = Depends(get_current_user),
    repo: DataRepository = Depends(get_data_repository),
) -> DataSourceFilesResponse:
    """Return CSV and XLSX files available in Azure Blob Storage."""
    return DataSourceFilesResponse.model_validate(
        list_data_source_files(current_user, tenant_id, repo)
    )


@router.post("/preview", response_model=DataSourcePreviewResponse)
def post_data_source_preview(
    payload: DataSourcePreviewRequest,
    current_user: CurrentUserContext = Depends(get_current_user),
    repo: DataRepository = Depends(get_data_repository),
) -> DataSourcePreviewResponse:
    """Preview a CSV or XLSX file and return non-blocking validation errors."""
    return DataSourcePreviewResponse.model_validate(
        preview_data_source_file(current_user, payload, repo)
    )
