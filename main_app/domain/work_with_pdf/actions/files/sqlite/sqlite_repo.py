import sqlite3
from pathlib import Path
from typing import Optional

from main_app.domain.work_with_pdf.actions.files.ports.run_repository import RunRow, RunRepository
from main_app.domain.work_with_pdf.actions.files.sqlite.schema import ensure_schema


class SqliteRunRepository(RunRepository):
    def __init__(self, db_path: Path):
        self.db_path = db_path.resolve()
        ensure_schema(self.db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def get(self, run_key: str) -> Optional[RunRow]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM runs WHERE run_key = ?",
                (run_key,),
            ).fetchone()
            return dict(row) if row else None

    def list_all(self) -> list[RunRow]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM runs ORDER BY created_at ASC").fetchall()
            return [dict(r) for r in rows]

    def upsert(self, row: RunRow) -> None:
        run_key = row["run_key"]
        status = row["status"]
        output_txt = row["output_txt"]

        sql = """
        INSERT INTO runs (run_key, status, output_txt)
        VALUES (?, ?, ?)
        ON CONFLICT(run_key) DO UPDATE SET
            status=excluded.status,
            output_txt=excluded.output_txt
        """
        values = (run_key, status, output_txt)

        with self._connect() as conn:
            conn.execute(sql, values)
            conn.commit()
