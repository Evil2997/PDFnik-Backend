import sqlite3
from pathlib import Path
from typing import Any, Optional

from main_app.domain.work_with_pdf.actions.files.ports.run_repository import RunRow, RunRepository
from main_app.domain.work_with_pdf.actions.files.sqlite.schema import ensure_schema, RUN_COLUMNS


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
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY created_at ASC"
            ).fetchall()
            return [dict(r) for r in rows]

    def upsert(self, row: RunRow) -> None:
        # нормализуем: берём только известные колонки
        data: dict[str, Any] = {k: row.get(k) for k in RUN_COLUMNS}

        # SQLite не имеет bool-типа: приводим vad к int если надо
        if data.get("vad") is not None:
            data["vad"] = int(bool(data["vad"]))

        cols = [c for c in RUN_COLUMNS if c != "run_key"]  # run_key отдельно
        placeholders = ", ".join(["?"] * (1 + len(cols)))  # run_key + cols
        col_list = ", ".join(["run_key"] + list(cols))

        # update без created_at (чтобы insert-time фиксировался)
        update_cols = [c for c in cols if c != "created_at"]
        update_clause = ", ".join([f"{c}=excluded.{c}" for c in update_cols])

        values = [data["run_key"]] + [data[c] for c in cols]

        sql = f"""
        INSERT INTO runs ({col_list})
        VALUES ({placeholders})
        ON CONFLICT(run_key) DO UPDATE SET
            {update_clause}
        """

        with self._connect() as conn:
            conn.execute(sql, values)
            conn.commit()
