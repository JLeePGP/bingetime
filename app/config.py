"""Environment-driven application settings."""
from __future__ import annotations

from pydantic import field_validator
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

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, v: str) -> str:
        """Managed hosts (Railway/Heroku) hand out `postgres://` or
        `postgresql://` URLs; SQLAlchemy needs the explicit psycopg-3 driver.
        Normalize so the raw provider URL can be pasted in as-is."""
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            v = "postgresql+psycopg://" + v[len("postgresql://"):]
        return v

    # TMDB — v3 API key or v4 bearer token. Empty disables enrichment.
    tmdb_api_key: str = ""
    tmdb_base_url: str = "https://api.themoviedb.org/3"
    tmdb_image_base: str = "https://image.tmdb.org/t/p/w500"

    # Static assets (versioned via content-hash query) get a long, immutable
    # cache. HTML pages get a short cache so deploys propagate in minutes.
    public_cache_seconds: int = 300
    page_cache_seconds: int = 300

    # Comma-separated emails allowed into the story-moderation queue.
    admin_emails: str = ""

    # Absolute site origin, used to build links in outgoing email (reset, etc.).
    base_url: str = "http://127.0.0.1:8000"

    # Transactional email via Resend (https://resend.com). Empty disables
    # sending — the reset link is logged instead so local dev still works.
    resend_api_key: str = ""
    email_from: str = "BingeTime <noreply@bingetime.tv>"

    # Microsoft Clarity project id — when set, the analytics snippet renders.
    clarity_project_id: str = ""

    # --- Blog content agent (Claude) ------------------------------------
    # Dedicated key so this agent's spend is isolated/trackable on the
    # Anthropic dashboard. Empty disables generation (the admin UI still
    # lists/edits posts; the Generate panel reports it's not configured).
    claude_blog_agent_api_key: str = ""
    # Single swap-point for the model. Sonnet 5 is the cost/quality pick;
    # bump to claude-opus-4-8 for flagship posts.
    blog_agent_model: str = "claude-sonnet-5"
    # Effort per task (adaptive thinking depth). Drafting gets more than
    # the lighter title-ideation pass.
    blog_agent_draft_effort: str = "high"
    blog_agent_title_effort: str = "medium"

    @property
    def blog_agent_enabled(self) -> bool:
        return bool(self.claude_blog_agent_api_key.strip())

    @property
    def admin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}


settings = Settings()
