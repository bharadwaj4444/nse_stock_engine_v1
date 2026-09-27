from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://nse:nse@localhost:5432/nse_stocks"
    nse_timeout_seconds: float = 30.0
    nse_max_retries: int = 4
    nse_throttle_seconds: float = 1.0
    raw_data_dir: Path = Path("data/raw")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
