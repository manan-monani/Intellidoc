"""
IntelliDoc Configuration
========================
Centralized settings management using pydantic-settings.
All config is loaded from environment variables / .env file.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── Application ──────────────────────────────────────────
    app_name: str = "IntelliDoc"
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "change-me-in-production"

    # ── Database ─────────────────────────────────────────────
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "intellidoc"
    db_user: str = "intellidoc_user"
    db_password: str = "intellidoc_pass"

    @property
    def database_url(self) -> str:
        """Async PostgreSQL connection string."""
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def database_url_sync(self) -> str:
        """Sync PostgreSQL URL for Alembic migrations."""
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # ── Redis ────────────────────────────────────────────────
    redis_host: str = "localhost"
    redis_port: int = 6379

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    # ── AWS ──────────────────────────────────────────────────
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "ap-south-1"
    s3_bucket_name: str = "intellidoc-documents"

    # ── ML Models ────────────────────────────────────────────
    ml_inference_mode: str = "local"  # "local" or "bedrock"
    huggingface_cache_dir: str = "./ml/models_cache"

    # ── AWS Bedrock ──────────────────────────────────────────
    bedrock_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"
    bedrock_embed_model_id: str = "amazon.titan-embed-text-v2:0"

    # ── Groq (Free LLM API) ──────────────────────────────────
    groq_api_key: str = ""
    groq_model_id: str = "llama-3.3-70b-versatile"

    # ── RAG Pipeline ─────────────────────────────────────────
    faiss_index_path: str = "./rag/faiss_index"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_provider: str = "local"  # "local" or "bedrock"
    llm_provider: str = "ollama"  # "ollama", "bedrock", or "groq"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "mistral"

    # ── JWT Auth ─────────────────────────────────────────────
    jwt_secret_key: str = "change-me-jwt-secret"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    # ── CORS ─────────────────────────────────────────────────
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    # ── File Upload ──────────────────────────────────────────
    max_upload_size_mb: int = 50
    allowed_extensions: str = "pdf,png,jpg,jpeg,tiff,docx"

    @property
    def allowed_extensions_list(self) -> List[str]:
        return [ext.strip() for ext in self.allowed_extensions.split(",")]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    Cached settings singleton.
    Call this function anywhere you need config values.

    Example:
        settings = get_settings()
        print(settings.database_url)
    """
    return Settings()
