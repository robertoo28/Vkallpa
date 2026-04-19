from typing import List, Tuple
import io
import logging
import threading
import time

import pandas as pd
from cachetools import TTLCache

from ..core.cache import make_ttl_cache
from ..core.azure import AzureBlobClient


class AzureDataError(RuntimeError):
    pass


class BuildingAccessError(PermissionError):
    pass


class DataRepository:
    def __init__(self, ttl_seconds: int = 600) -> None:
        self._client = AzureBlobClient()
        self._blob_cache: TTLCache = make_ttl_cache(maxsize=1, ttl_seconds=ttl_seconds)
        self._df_cache: TTLCache = make_ttl_cache(maxsize=128, ttl_seconds=ttl_seconds)
        self._range_cache: TTLCache = make_ttl_cache(maxsize=256, ttl_seconds=ttl_seconds)
        self._lock = threading.RLock()
        self._inflight: dict[str, threading.Event] = {}
        self._download_semaphore = threading.Semaphore(2)

    def list_blobs(self) -> List[str]:
        with self._lock:
            if "blobs" in self._blob_cache:
                return self._blob_cache["blobs"]
        try:
            for attempt in range(3):
                try:
                    container = self._client.get_container_client()
                    blobs = [b.name for b in container.list_blobs()]
                    with self._lock:
                        self._blob_cache["blobs"] = blobs
                    return blobs
                except Exception:
                    if attempt == 2:
                        logging.exception("Failed to list blobs")
                        raise
                    time.sleep(0.5 * (2**attempt))
        except Exception as exc:
            raise AzureDataError(str(exc))

    def download_blob_bytes(self, blob_name: str) -> bytes:
        try:
            for attempt in range(3):
                try:
                    with self._download_semaphore:
                        container = self._client.get_container_client()
                        blob_client = container.get_blob_client(blob_name)
                        return blob_client.download_blob().readall()
                except Exception:
                    if attempt == 2:
                        logging.exception("Failed to download blob %s", blob_name)
                        raise
                    time.sleep(0.5 * (2**attempt))
        except Exception as exc:
            raise AzureDataError(str(exc))

    def load_excel(self, blob_name: str, sheet_name: str) -> pd.DataFrame:
        cache_key = f"{blob_name}:{sheet_name}"
        with self._lock:
            if cache_key in self._df_cache:
                return self._df_cache[cache_key].copy()
            if cache_key in self._inflight:
                event = self._inflight[cache_key]
                wait = True
            else:
                event = threading.Event()
                self._inflight[cache_key] = event
                wait = False

        if wait:
            event.wait()
            with self._lock:
                if cache_key in self._df_cache:
                    return self._df_cache[cache_key].copy()
            try:
                data = self.download_blob_bytes(blob_name)
                df = pd.read_excel(io.BytesIO(data), sheet_name=sheet_name, engine="openpyxl")
            except Exception as exc:
                logging.exception(
                    "Failed to load Excel sheet %s from %s after inflight wait",
                    sheet_name,
                    blob_name,
                )
                raise AzureDataError(str(exc))
            with self._lock:
                self._df_cache[cache_key] = df
            return df.copy()

        try:
            data = self.download_blob_bytes(blob_name)
            df = pd.read_excel(io.BytesIO(data), sheet_name=sheet_name, engine="openpyxl")
        except Exception as exc:
            logging.exception("Failed to load Excel sheet %s from %s", sheet_name, blob_name)
            raise AzureDataError(str(exc))
        finally:
            with self._lock:
                event.set()
                self._inflight.pop(cache_key, None)

        with self._lock:
            self._df_cache[cache_key] = df
        return df.copy()

    def get_date_range(self, blob_name: str) -> Tuple[str, str]:
        cache_key = f"{blob_name}:range"
        with self._lock:
            if cache_key in self._range_cache:
                return self._range_cache[cache_key]

        df = self.load_excel(blob_name, sheet_name="Donnees_Detaillees")
        if "Date" not in df.columns:
            raise AzureDataError("Missing Date column")
        df["Date"] = pd.to_datetime(df["Date"])
        result = (df["Date"].min().date().isoformat(), df["Date"].max().date().isoformat())
        with self._lock:
            self._range_cache[cache_key] = result
        return result


_DEFAULT_REPO: DataRepository | None = None


def get_repo() -> DataRepository:
    global _DEFAULT_REPO
    if _DEFAULT_REPO is None:
        _DEFAULT_REPO = DataRepository()
    return _DEFAULT_REPO


class ScopedDataRepository:
    def __init__(self, repo: DataRepository, allowed_buildings: list[str] | None) -> None:
        self._repo = repo
        self._allowed_buildings = None if allowed_buildings is None else set(allowed_buildings)

    def _assert_access(self, blob_name: str) -> None:
        if self._allowed_buildings is None:
            return
        if blob_name not in self._allowed_buildings:
            raise BuildingAccessError(f"Access denied for building {blob_name}")

    def list_blobs(self) -> List[str]:
        blobs = self._repo.list_blobs()
        if self._allowed_buildings is None:
            return blobs
        return [blob for blob in blobs if blob in self._allowed_buildings]

    def download_blob_bytes(self, blob_name: str) -> bytes:
        self._assert_access(blob_name)
        return self._repo.download_blob_bytes(blob_name)

    def load_excel(self, blob_name: str, sheet_name: str) -> pd.DataFrame:
        self._assert_access(blob_name)
        return self._repo.load_excel(blob_name, sheet_name)

    def get_date_range(self, blob_name: str) -> Tuple[str, str]:
        self._assert_access(blob_name)
        return self._repo.get_date_range(blob_name)
