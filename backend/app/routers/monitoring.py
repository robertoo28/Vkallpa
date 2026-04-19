import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..auth.dependencies import get_scoped_data_repository, require_module_access
from ..services.data_repository import AzureDataError
from ..services.monitoring import (
    build_monitoring_boxplots,
    build_monitoring_calendar,
    build_monitoring_graphs,
    build_monitoring_heatmap,
)
from ..services.monitoring_comparaison import build_comparaison_puissance


router = APIRouter()


@router.get("/monitoring/graphs")
def monitoring_graphs(
    building: str = Query(..., description="Blob file name"),
    start_date: str | None = Query(None, description="YYYY-MM-DD"),
    end_date: str | None = Query(None, description="YYYY-MM-DD"),
    metric: str = Query("Energie", description="Energie or Puissance"),
    aggregation: str = Query("Jour", description="Heure, Jour, Semaine, Mois, Annee"),
    show_vacances: bool = Query(True),
    repo=Depends(get_scoped_data_repository),
    _=Depends(require_module_access("monitoring")),
) -> dict:
    try:
        return build_monitoring_graphs(
            repo,
            building,
            start_date,
            end_date,
            metric,
            aggregation,
            show_vacances,
        )
    except AzureDataError:
        logging.exception("Azure error")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Azure error")


@router.get("/monitoring/heatmap")
def monitoring_heatmap(
    building: str = Query(..., description="Blob file name"),
    start_date: str | None = Query(None, description="YYYY-MM-DD"),
    end_date: str | None = Query(None, description="YYYY-MM-DD"),
    repo=Depends(get_scoped_data_repository),
    _=Depends(require_module_access("monitoring")),
) -> dict:
    try:
        return build_monitoring_heatmap(repo, building, start_date, end_date)
    except AzureDataError:
        logging.exception("Azure error")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Azure error")


@router.get("/monitoring/calendar")
def monitoring_calendar(
    building: str = Query(..., description="Blob file name"),
    start_date: str | None = Query(None, description="YYYY-MM-DD"),
    end_date: str | None = Query(None, description="YYYY-MM-DD"),
    repo=Depends(get_scoped_data_repository),
    _=Depends(require_module_access("monitoring")),
) -> dict:
    try:
        return build_monitoring_calendar(repo, building, start_date, end_date)
    except AzureDataError:
        logging.exception("Azure error")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Azure error")


@router.get("/monitoring/boxplots")
def monitoring_boxplots(
    building: str = Query(..., description="Blob file name"),
    start_date: str | None = Query(None, description="YYYY-MM-DD"),
    end_date: str | None = Query(None, description="YYYY-MM-DD"),
    repo=Depends(get_scoped_data_repository),
    _=Depends(require_module_access("monitoring")),
) -> dict:
    try:
        return build_monitoring_boxplots(repo, building, start_date, end_date)
    except AzureDataError:
        logging.exception("Azure error")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Azure error")


@router.get("/monitoring/comparaison-puissance")
def comparaison_puissance(
    building: str = Query(..., description="Blob file name"),
    reference_date: str = Query(..., description="YYYY-MM-DD"),
    comparison_dates: list[str] = Query([], description="YYYY-MM-DD list"),
    repo=Depends(get_scoped_data_repository),
    _=Depends(require_module_access("comparaison-puissance")),
) -> dict:
    try:
        return build_comparaison_puissance(
            repo,
            building,
            reference_date,
            comparison_dates,
        )
    except AzureDataError:
        logging.exception("Azure error")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Azure error")
