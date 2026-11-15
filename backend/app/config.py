from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HANDOFF_", extra="ignore")

    database_url: str = f"sqlite:///{(ROOT_DIR / 'data' / 'handoff.db').as_posix()}"
    demo_mode: bool = True
    generation_timeout_seconds: int = 60
    max_upload_bytes: int = 1024 * 1024
    max_generation_characters: int = 20_000
    frontend_dist: Path = ROOT_DIR / "frontend" / "dist"


settings = Settings()
