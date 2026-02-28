import sqlite3
from pathlib import Path

RUN_COLUMNS: tuple[str, ...] = (
    "run_key",
    "status",
    "error",
    "target_id",
    "output_txt",
    "model",
    "device",
    "compute_type",
    "threads",
    "workers",
    "beam_size",
    "patience",
    "vad",
    "lang",
    "detected_language",
    "wall_time_sec",
    "audio_duration_sec",
    "rtf",
    "wer",
    "cer",
)

_SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS runs (
    run_key TEXT PRIMARY KEY,

    status TEXT NOT NULL,
    error TEXT,

    target_id TEXT NOT NULL,
    output_txt TEXT NOT NULL,

    model TEXT NOT NULL,
    device TEXT NOT NULL,
    compute_type TEXT,

    threads INTEGER,
    workers INTEGER,
    beam_size INTEGER,
    patience REAL,
    vad INTEGER,
    lang TEXT,
    detected_language TEXT,

    wall_time_sec REAL,
    audio_duration_sec REAL,
    rtf REAL,

    wer REAL,
    cer REAL,

    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_runs_target_id ON runs(target_id);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
"""


def ensure_schema(db_path: Path) -> None:
    db_path = db_path.resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
