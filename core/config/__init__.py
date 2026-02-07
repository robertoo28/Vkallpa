import json
import os
from dotenv import load_dotenv

_config = None

def get_config():
    global _config
    if _config is None:
        # Load environment variables from .env file
        load_dotenv()

        # Get the environment setting
        env = os.getenv('APP_ENV', 'dev')  # Default to 'dev' if not set
        config_filename = f'config.{env}.json'

        # Build the path to the config file
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), config_filename)

        # Load the config file
        with open(config_path, 'r') as f:
            _config = json.load(f)

    return _config