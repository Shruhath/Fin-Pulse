from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVER_DIR = Path(__file__).resolve().parents[3]
REPO_DIR = SERVER_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FINPULSE_",
        env_file=SERVER_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://finpulse:finpulse@127.0.0.1:5433/finpulse"

    data_dir: Path = REPO_DIR / "data"
    corpus_dir: Path = REPO_DIR / "data-set" / "layer2"
    benchmark_dir: Path = REPO_DIR / "data-set" / "layer1"

    ollama_url: str = "http://127.0.0.1:11434"
    event_model: str = "qwen2.5:7b-instruct"
    summary_model: str = "llama3.1:8b-instruct"

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # A PDF page with fewer words than this has no usable text layer and goes through OCR.
    ocr_min_words_per_page: int = Field(default=20, ge=0)
    ocr_dpi: int = Field(default=200, ge=72)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"


@lru_cache
def get_settings() -> Settings:
    return Settings()
