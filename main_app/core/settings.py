from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # RabbitMQ connection URL
    RABBITMQ_URL: str

    # SQLite path (volume). Minimal cache for idempotency only.
    SQLITE_PATH: str = Field(
        default="/data_files_storage/runs.sqlite3",
        description="SQLite файл в общем volume. Используется как минимальный кэш idempotency.",
    )

    # ------------------------------------------------------------
    # Transcribe defaults (простые, потом ты настроишь как нужно)
    # Всё управляется через .env
    # ------------------------------------------------------------
    TRANSCRIBE_MODEL: str = Field(default="base", description="Whisper model name.")
    TRANSCRIBE_DEVICE: str = Field(default="cpu", description="cpu | cuda")
    TRANSCRIBE_COMPUTE_TYPE: str | None = Field(default=None, description="None -> auto")

    TRANSCRIBE_THREADS: int = Field(default=4, ge=1)
    TRANSCRIBE_WORKERS: int = Field(default=1, ge=1)
    TRANSCRIBE_BEAM_SIZE: int = Field(default=5, ge=1)
    TRANSCRIBE_PATIENCE: float = Field(default=1.0, ge=0.0)
    TRANSCRIBE_VAD: bool = Field(default=False)
    TRANSCRIBE_LANG: str = Field(default="auto")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
