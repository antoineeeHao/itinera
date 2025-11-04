# Environment configuration loader for ITINERA
import os
from typing import Optional

def load_env_file(file_path: str = ".env") -> None:
    """Load environment variables from .env file"""
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
    except FileNotFoundError:
        pass  # .env file is optional

def get_env_var(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get environment variable with optional default"""
    return os.getenv(key, default)

# Load environment variables on import
load_env_file()