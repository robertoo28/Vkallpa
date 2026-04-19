import logging

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth.dependencies import get_scoped_data_repository, require_module_access
from ..services.dashboard_multi import build_dashboard_multi_summary
from ..services.data_repository import AzureDataError


router = APIRouter()


@router.get("/dashboard-multi/summary")
def dashboard_multi_summary(
    repo=Depends(get_scoped_data_repository),
    _=Depends(require_module_access("parc-immobilier")),
) -> dict:
    try:
        return build_dashboard_multi_summary(repo)
    except AzureDataError:
        logging.exception("Azure error")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Azure error")
