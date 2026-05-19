from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path

ENV_FILE = Path(__file__).parent / ".env"


class Settings(BaseSettings):
    at_username: str = "sandbox"
    at_api_key: str = ""
    at_shortcode: str = "HoLo"
    at_wa_number: str = ""

    gemini_api_key: str = ""
    google_places_api_key: str = ""

    paystack_secret_key: str = ""

    app_env: str = "development"
    app_port: int = 8000
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/postgres"
    groq_api_key: str = ""

    class Config:
        env_file = str(ENV_FILE)
        case_sensitive = False
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
