from azure.storage.blob import BlobServiceClient
from .config import load_azure_config


class AzureBlobClient:
    def __init__(self) -> None:
        cfg = load_azure_config()
        self._connection_string = cfg["connection_string"]
        self._container_name = cfg["container_name"]
        self._service_client = BlobServiceClient.from_connection_string(self._connection_string)

    @property
    def container_name(self) -> str:
        return self._container_name

    def get_container_client(self):
        return self._service_client.get_container_client(self._container_name)
