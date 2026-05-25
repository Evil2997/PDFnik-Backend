from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # RabbitMQ connection URL
    RABBITMQ_URL: str

    # SQLite path (shared Docker volume). Minimal idempotency cache.
    SQLITE_PATH: str = Field(
        default="/data_files_storage/runs.sqlite3",
        description="SQLite file on the shared volume. Used as a minimal idempotency cache.",
    )

    # ---------------------------------------------------------------------------
    # Whisper transcription defaults — all overridable via .env
    # ---------------------------------------------------------------------------
    TRANSCRIBE_MODEL: str = Field(default="base", description="Whisper model name.")
    TRANSCRIBE_DEVICE: str = Field(default="cpu", description="cpu | cuda")
    TRANSCRIBE_COMPUTE_TYPE: str | None = Field(default=None, description="None -> auto")

    TRANSCRIBE_THREADS: int = Field(default=4, ge=1)
    TRANSCRIBE_WORKERS: int = Field(default=1, ge=1)
    TRANSCRIBE_BEAM_SIZE: int = Field(default=5, ge=1)
    TRANSCRIBE_PATIENCE: float = Field(default=1.0, ge=0.0)
    TRANSCRIBE_VAD: bool = Field(default=False)
    TRANSCRIBE_LANG: str = Field(default="auto")

    # ---------------------------------------------------------------------------
    # LLM summary — optional YouTube transcript summarization
    # SUMMARY_PROVIDER: disabled | anthropic | openai | ollama
    # ---------------------------------------------------------------------------
    SUMMARY_PROVIDER: str = Field(default="disabled")
    ANTHROPIC_API_KEY: str | None = Field(default=None)
    OPENAI_API_KEY: str | None = Field(default=None)
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434")
    OLLAMA_MODEL: str = Field(default="llama3.2")
    SUMMARY_MAX_CHARS: int = Field(default=6000, ge=100)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
