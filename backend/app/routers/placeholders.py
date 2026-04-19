from fastapi import APIRouter, HTTPException, status


router = APIRouter()


def _not_implemented():
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")
