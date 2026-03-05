import sqlite3
from pathlib import Path

RUN_COLUMNS: tuple[str, ...] = (
    "run_key",
    "status",
    "output_txt",
    "created_at",
)

_SCHEMA_SQL_MIN = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS runs (
    run_key TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    output_txt TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
"""


def _get_existing_columns(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("PRAGMA table_info(runs);").fetchall()
    return [r[1] for r in rows]


def _needs_migration(existing_cols: list[str]) -> bool:
    if not existing_cols:
        return False
    return set(existing_cols) != set(RUN_COLUMNS)


def ensure_schema(db_path: Path) -> None:
    db_path = db_path.resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(db_path)) as conn:
        existing_cols = _get_existing_columns(conn)

        if not existing_cols:
            conn.executescript(_SCHEMA_SQL_MIN)
            conn.commit()
            return

        if _needs_migration(existing_cols):
            conn.execute("ALTER TABLE runs RENAME TO runs_old;")
            conn.executescript(_SCHEMA_SQL_MIN)

            cols_old = set(existing_cols)

            insert_cols = ["run_key", "status", "output_txt"]
            select_cols = ["run_key", "status", "output_txt"]

            if "created_at" in cols_old:
                insert_cols.append("created_at")
                select_cols.append("created_at")

            conn.execute(
                f"""
                INSERT INTO runs ({", ".join(insert_cols)})
                SELECT {", ".join(select_cols)}
                FROM runs_old;
                """
            )

            conn.execute("DROP TABLE runs_old;")
            conn.commit()
            return

        conn.executescript(_SCHEMA_SQL_MIN)
        conn.commit()
