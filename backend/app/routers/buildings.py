import logging

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth.dependencies import get_scoped_data_repository
from ..services.data_repository import AzureDataError, DataRepository, ScopedDataRepository


router = APIRouter()


@router.get("/buildings")
def list_buildings(
    repo: DataRepository | ScopedDataRepository = Depends(get_scoped_data_repository),
) -> dict:
    try:
        blobs = repo.list_blobs()
    except AzureDataError:
        logging.exception("Azure error")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Azure error")

    items = []
    for name in blobs:
        if name.lower().endswith((".xlsx", ".xls")):
            label = name.rsplit(".", 1)[0]
            items.append({"id": name, "label": label})

    return {"items": items}


@router.get("/buildings/{blob_id:path}/range")
def get_range(
    blob_id: str,
    repo: DataRepository | ScopedDataRepository = Depends(get_scoped_data_repository),
) -> dict:
    try:
        min_date, max_date = repo.get_date_range(blob_id)
    except AzureDataError:
        logging.exception("Azure error")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Azure error")

    return {"min_date": min_date, "max_date": max_date}
