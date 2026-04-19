import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..auth.dependencies import get_scoped_data_repository, require_module_access
from ..services.data_repository import AzureDataError
from ..services.nilm import build_nilm


router = APIRouter()


class NilmRequest(BaseModel):
    building: str
    start_date: str | None = None
    end_date: str | None = None
    aggregation: str = "Jour"


@router.post("/ia/nilm")
def nilm(
    payload: NilmRequest,
    repo=Depends(get_scoped_data_repository),
    _=Depends(require_module_access("nilm")),
) -> dict:
    try:
        return build_nilm(
            repo,
            payload.building,
            payload.start_date,
            payload.end_date,
            payload.aggregation,
        )
    except AzureDataError:
        logging.exception("Azure error")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Azure error")
