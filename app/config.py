"""Environment-driven application settings."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "BingeTime"
    debug: bool = True
    secret_key: str = "change-me-before-deploy"

    # Postgres (SQLAlchemy URL, psycopg 3 driver).
    database_url: str = (
        "postgresql+psycopg://bingetime:bingetime@localhost:5432/bingetime"
    )

    # TMDB — v3 API key or v4 bearer token. Empty disables enrichment.
    tmdb_api_key: str = ""
    tmdb_base_url: str = "https://api.themoviedb.org/3"
    tmdb_image_base: str = "https://image.tmdb.org/t/p/w500"

    # Public pages get this max-age (seconds) for CDN/browser caching.
    public_cache_seconds: int = 300

    # Comma-separated emails allowed into the story-moderation queue.
    admin_emails: str = ""

    @property
    def admin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}


settings = Settings()
