import logging

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth.dependencies import get_scoped_data_repository, require_module_access
from ..services.accueil import build_accueil_summary
from ..services.data_repository import AzureDataError


router = APIRouter()


@router.get("/accueil/summary")
def accueil_summary(
    repo=Depends(get_scoped_data_repository),
    _=Depends(require_module_access("accueil")),
) -> dict:
    try:
        return build_accueil_summary(repo)
    except AzureDataError:
        logging.exception("Azure error")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Azure error")
