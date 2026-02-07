# File: logic/azure_data_loader.py

from azure.storage.blob import BlobServiceClient
import pandas as pd
import numpy as np
from scipy import stats

class DataLoader:
    def __init__(self, connection_string, container_name):
        self.connection_string = connection_string
        self.container_name = container_name
        self.blob_service_client = self._init_azure_client()

    def _init_azure_client(self):
        """Initialize the Azure Blob Service Client."""
        return BlobServiceClient.from_connection_string(self.connection_string)

    def get_blob_list(self):
        """Retrieve the list of blobs in the container."""
        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
            return [blob.name for blob in container_client.list_blobs()]
        except Exception as e:
            print(f"Error retrieving blob list: {e}")
            return []

    def load_data(self, blob_name, sheet_name='Donnees_Detaillees', threshold=50):
        """Load data from a blob and clean outliers."""
        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
            blob_client = container_client.get_blob_client(blob_name)
            data = blob_client.download_blob().readall()
            df = pd.read_excel(data, sheet_name=sheet_name)
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            return self._replace_outliers_with_mean(df, threshold)
        except Exception as e:
            print(f"Error loading data: {e}")
            return pd.DataFrame()

    def _replace_outliers_with_mean(self, df, threshold):
        """Replace outliers in numeric columns with the column mean."""
        df_cleaned = df.copy()
        numeric_cols = df_cleaned.select_dtypes(include=[np.number]).columns

        for col in numeric_cols:
            col_mean = df_cleaned[col].mean()
            z_scores = np.abs(stats.zscore(df_cleaned[col]))
            df_cleaned[col] = df_cleaned[col].mask(z_scores > threshold, col_mean)

        return df_cleaned