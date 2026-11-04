"""Runtime settings, read from environment variables and then from a .env file."""

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment variables win over values in .env. Unknown variables are ignored.

    Keys are optional, so commands that don't call an API run without any keys set.
    Code that needs a key checks for it before use.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    data_dir: Path = Path("data")
    mistral_api_key: SecretStr | None = None
