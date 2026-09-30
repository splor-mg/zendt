import os
from pathlib import Path

import dotenv


def load_env(start: Path | None = None) -> None:
    """Load environment variables from .env file (if any)"""
    if start is None:
        start = Path.cwd()
    env_file = start / '.env'
    if env_file.exists():
        dotenv.load_dotenv(env_file)


def get_env_var(var_name: str | None) -> str | None:
    var = os.environ.get(var_name)
    return var
