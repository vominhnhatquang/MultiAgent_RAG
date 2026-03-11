from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.dev"),  # .env.dev overrides .env when present
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "RAG Chatbot API"
    app_version: str = "0.1.0"
    debug: bool = False

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "ragdb"
    postgres_user: str = "raguser"
    postgres_password: str = "ragpass"

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def postgres_dsn_sync(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "document_chunks"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_chat_model: str = "gemma2:2b"
    ollama_timeout: int = 120

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"

    # Force a specific LLM backend for testing: "gemini" | "ollama" | "" (auto)
    force_llm_backend: str = ""

    # Dev mode — no Docker needed: SQLite + in-memory Qdrant + fakeredis
    dev_mode: bool = False

    @property
    def sqlite_dsn(self) -> str:
        return "sqlite+aiosqlite:///./dev.db"

    # Upload limits
    max_upload_size_mb: int = 50
    allowed_file_types: list[str] = ["pdf", "docx", "md", "txt"]

    # Chunking
    chunk_size: int = 512          # tokens
    chunk_overlap: int = 64        # tokens

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # Rate limiting
    rate_limit_chat: int = 10       # per minute
    rate_limit_upload: int = 5      # per minute
    rate_limit_default: int = 60    # per minute


settings = Settings()
