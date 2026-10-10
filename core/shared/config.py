"""OMNIVERSO Core — Shared Configuration Module."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ─── Service Identity ─────────────────────────────────
    service_name: str = "omniverso-core"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True

    # ─── Database ─────────────────────────────────────────
    db_url: str = "postgresql+asyncpg://omniverso:omniverso_dev_2024@localhost:5432/omniverso"

    # ─── Redis ────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/1"

    # ─── Qdrant ───────────────────────────────────────────
    qdrant_url: str = "http://localhost:6333"

    # ─── Model Router ─────────────────────────────────────
    model_router_url: str = "http://localhost:8002"

    # ─── AI Providers ─────────────────────────────────────
    gemini_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    openrouter_api_key: str = ""

    # ─── Defaults ─────────────────────────────────────────
    default_provider: str = "gemini"
    default_model: str = "gemini-2.5-flash"

    @property
    def available_providers(self) -> list[str]:
        """Return list of providers with configured API keys."""
        providers = []
        if self.gemini_api_key:
            providers.append("gemini")
        if self.openai_api_key:
            providers.append("openai")
        if self.anthropic_api_key:
            providers.append("anthropic")
        if self.openrouter_api_key:
            providers.append("openrouter")
        return providers


@lru_cache
def get_settings() -> Settings:
    """Singleton settings instance."""
    return Settings()
