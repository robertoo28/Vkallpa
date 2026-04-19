import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..auth.dependencies import get_scoped_data_repository, require_module_access
from ..services.data_repository import AzureDataError
from ..services.puissance import build_puissance


router = APIRouter()


@router.get("/puissance")
def puissance(
    building: str = Query(..., description="Blob file name"),
    start_date: str | None = Query(None, description="YYYY-MM-DD"),
    end_date: str | None = Query(None, description="YYYY-MM-DD"),
    repo=Depends(get_scoped_data_repository),
    _=Depends(require_module_access("puissance-max")),
) -> dict:
    try:
        return build_puissance(repo, building, start_date, end_date)
    except AzureDataError:
        logging.exception("Azure error")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Azure error")
