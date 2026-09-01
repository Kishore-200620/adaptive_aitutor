from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# backend/app/core/config.py
# parents[0] = core
# parents[1] = app
# parents[2] = backend
# parents[3] = EDUVA project root

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    app_name: str = "EDUVA"
    app_env: str = "development"
    debug: bool = True

    database_url: str
    groq_api_key: str

    upload_dir: str = "storage/uploads"

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()