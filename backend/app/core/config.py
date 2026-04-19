import json
from pathlib import Path


class AzureConfigError(RuntimeError):
    pass


def load_azure_config() -> dict:
    root = Path(__file__).resolve().parents[3]
    config_path = root / "config.dev.json"
    if not config_path.exists():
        raise AzureConfigError(f"config.dev.json not found at {config_path}")

    data = json.loads(config_path.read_text(encoding="utf-8"))
    azure = data.get("azure")
    if not azure:
        raise AzureConfigError("Missing 'azure' section in config.dev.json")

    if "connection_string" not in azure or "container_name" not in azure:
        raise AzureConfigError("Azure config must include connection_string and container_name")

    return azure
