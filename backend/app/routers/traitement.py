import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..auth.dependencies import get_scoped_data_repository, require_module_access
from ..services.data_repository import AzureDataError
from ..services.traitement_batiments import build_batiments
from ..services.traitement_comparaison import build_comparaison_periode


router = APIRouter()


@router.get("/traitement/comparaison-periode")
def comparaison_periode(
    building: str = Query(..., description="Blob file name"),
    start_a: str = Query(..., description="YYYY-MM-DD"),
    end_a: str = Query(..., description="YYYY-MM-DD"),
    start_b: str = Query(..., description="YYYY-MM-DD"),
    end_b: str = Query(..., description="YYYY-MM-DD"),
    metric: str = Query("Energie", description="Energie or Puissance"),
    normalize_days: bool = Query(True),
    exclude_weekends: bool = Query(False),
    repo=Depends(get_scoped_data_repository),
    _=Depends(require_module_access("comparaison-periode")),
) -> dict:
    try:
        return build_comparaison_periode(
            repo,
            building,
            start_a,
            end_a,
            start_b,
            end_b,
            metric,
            normalize_days,
            exclude_weekends,
        )
    except AzureDataError:
        logging.exception("Azure error")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Azure error")


@router.get("/traitement/batiments")
def batiments(
    buildings: list[str] = Query([], description="Blob file names"),
    start_date: str | None = Query(None, description="YYYY-MM-DD"),
    end_date: str | None = Query(None, description="YYYY-MM-DD"),
    metric: str = Query("Energie", description="Energie or Puissance"),
    aggregation: str = Query("Jour", description="Heure, Jour, Semaine, Mois, Annee"),
    normalize: bool = Query(False),
    repo=Depends(get_scoped_data_repository),
    _=Depends(require_module_access("comparatif-batiments")),
) -> dict:
    try:
        return build_batiments(
            repo,
            buildings,
            start_date,
            end_date,
            metric,
            aggregation,
            normalize,
        )
    except AzureDataError:
        logging.exception("Azure error")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Azure error")
