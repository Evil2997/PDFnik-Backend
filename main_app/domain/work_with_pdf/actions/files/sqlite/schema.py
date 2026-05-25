import sqlite3
from pathlib import Path

RUN_COLUMNS: tuple[str, ...] = (
    "run_key",
    "status",
    "output_txt",
    "created_at",
)

# Used only for initial creation (not inside a migration transaction).
_SCHEMA_SQL_INITIAL = """
CREATE TABLE IF NOT EXISTS runs (
    run_key    TEXT PRIMARY KEY,
    status     TEXT NOT NULL,
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


def _run_migration(conn: sqlite3.Connection, existing_cols: list[str]) -> None:
    """
    Runs DDL migration: rename → create → copy → drop → index.
    Called under BEGIN EXCLUSIVE — atomic operation.
    """
    conn.execute("ALTER TABLE runs RENAME TO runs_old")

    conn.execute("""
        CREATE TABLE runs (
            run_key    TEXT PRIMARY KEY,
            status     TEXT NOT NULL,
            output_txt TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        )
    """)

    # Copy only columns present in both schema versions.
    cols_old = set(existing_cols)
    copy_cols = ["run_key", "status", "output_txt"]
    if "created_at" in cols_old:
        copy_cols.append("created_at")

    cols_str = ", ".join(copy_cols)
    conn.execute(f"INSERT INTO runs ({cols_str}) SELECT {cols_str} FROM runs_old")
    conn.execute("DROP TABLE runs_old")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status)")


def ensure_schema(db_path: Path) -> None:
    db_path = db_path.resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # isolation_level=None → autocommit; PRAGMAs must run outside a transaction,
    # and BEGIN EXCLUSIVE is only needed explicitly for migration.
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    try:
        # PRAGMAs must run outside a transaction.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

        existing_cols = _get_existing_columns(conn)

        if not existing_cols:
            # Fresh DB — create schema.
            conn.executescript(_SCHEMA_SQL_INITIAL)
            return

        if _needs_migration(existing_cols):
            # Run the full migration inside one EXCLUSIVE transaction.
            # executescript() issues an implicit COMMIT before running, which
            # could leave the DB half-broken on a crash (runs_old exists, runs does not).
            conn.execute("BEGIN EXCLUSIVE")
            try:
                _run_migration(conn, existing_cols)
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            return

        # Schema is up to date — nothing to do (indexes already created on init).

    finally:
        conn.close()
